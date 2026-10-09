#!/usr/bin/env python3
"""Add a Windows host to an existing index without rebuilding Mac assets."""
import argparse
import copy
import hashlib
import io
import json
import pathlib
import struct
import tarfile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=pathlib.Path, required=True)
    parser.add_argument('--uploader', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    data = args.uploader.read_bytes()
    if data[:2] != b'MZ':
        parser.error('Expected a Windows PE executable')
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0x8664:
        parser.error('Expected a Windows x86-64 executable')
    original = json.loads(args.index.read_text())
    index = copy.deepcopy(original)
    package = next(p for p in index['packages'] if p['name'] == 'TerrainTronics')
    tool = next(t for t in package['tools'] if t['name'] == 'tt-upload' and t['version'] == '0.1.0')
    if any(s['host'] == 'x86_64-mingw32' for s in tool['systems']):
        parser.error('Windows entry already exists')
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / 'tt-upload-0.1.0-windows-x86_64.tar.gz'
    # Fixed archive metadata makes repeated packaging of the same EXE stable.
    import gzip
    with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as tar:
            entry = tarfile.TarInfo('tt-upload/tt-upload.exe')
            entry.size = len(data)
            entry.mode = 0o755
            tar.addfile(entry, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    tool['systems'].append(dict(host='x86_64-mingw32',
        url='https://github.com/Audio-Rochey/TT-Holt-Castle-ArduinoBootloader/releases/download/arduino-0.1.0/' + archive.name,
        archiveFileName=archive.name, checksum='SHA-256:' + checksum, size=str(archive.stat().st_size)))
    assert package['platforms'] == original['packages'][0]['platforms']
    assert tool['systems'][:-1] == next(t for t in original['packages'][0]['tools'] if t['name'] == 'tt-upload')['systems']
    output_index = args.output / 'package_terraintronics_index.json'
    output_index.write_text(json.dumps(index, indent=2) + '\n')
    (args.output / 'SHA256SUMS-windows.txt').write_text(checksum + '  ' + archive.name + '\n' + hashlib.sha256(data).hexdigest() + '  tt-upload.exe\n')
    print(args.output.resolve())

if __name__ == '__main__':
    main()
