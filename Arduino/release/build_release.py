#!/usr/bin/env python3
"""Package the hardware-tested platform snapshot and standalone uploader."""
import argparse, hashlib, json, pathlib, tarfile, tempfile, zipfile, shutil, struct

VERSION = '0.1.0'
REPO = 'https://github.com/Audio-Rochey/TT-Holt-Castle-ArduinoBootloader'
TAG = 'arduino-' + VERSION

def digest(path):
    return 'SHA-256:' + hashlib.sha256(path.read_bytes()).hexdigest()

def archive(root, output):
    with tarfile.open(output, 'w:gz') as tar:
        tar.add(root, arcname=root.name)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--platform', type=pathlib.Path, required=True)
    p.add_argument('--uploader', type=pathlib.Path, required=True)
    p.add_argument('--output', type=pathlib.Path, default=pathlib.Path('release-assets'))
    a = p.parse_args()
    header = a.uploader.read_bytes()[:8]
    if header[:4] != bytes.fromhex('cffaedfe') or struct.unpack('<I', header[4:])[0] != 0x100000c:
        p.error('Expected a macOS arm64 Mach-O uploader')
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        base = pathlib.Path(temp)
        core = base / ('holt-castle-' + VERSION)
        core.mkdir()
        with zipfile.ZipFile(a.platform) as z:
            for item in z.infolist():
                path = pathlib.PurePosixPath(item.filename)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe archive path')
                if any(part == '__MACOSX' or part == '.DS_Store' or part.startswith('._') for part in path.parts):
                    continue
                if path.parts[0] == 'tools' or path.name == 'TT_HOLT_INSTALL.json':
                    continue
                target = core.joinpath(*path.parts)
                if item.is_dir(): target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(item))
        for required in ('boards.txt', 'platform.txt', 'cores/arduino/tt_bootload_hook.c', 'variants/CH32VM00X/HoltCastle/variant_HoltCastle.h'):
            if not (core / required).is_file(): raise ValueError('Missing ' + required)
        local = core / 'platform.local.txt'
        content = local.read_text().replace('tools.ttupload.path={runtime.platform.path}/tools/ttupload/{ttupload.host}', 'tools.ttupload.path={runtime.tools.tt-upload.path}')
        local.write_text(content)
        platform_archive = a.output / ('holt-castle-' + VERSION + '.tar.gz')
        archive(core, platform_archive)
        tool = base / 'tt-upload'
        tool.mkdir()
        shutil.copyfile(a.uploader, tool / 'tt-upload')
        (tool / 'tt-upload').chmod(0o755)
        tool_archive = a.output / ('tt-upload-' + VERSION + '-macos-arm64.tar.gz')
        archive(tool, tool_archive)
    upstream = json.loads(pathlib.Path(__file__).with_name('wch-package-index.json').read_text())
    compiler = next(t for p in upstream['packages'] for t in p.get('tools', []) if t['name'] == 'riscv-none-embed-gcc' and t['version'] == '8.2.0')
    def asset(path):
        return dict(url=REPO + '/releases/download/' + TAG + '/' + path.name, archiveFileName=path.name, checksum=digest(path), size=str(path.stat().st_size))
    # Distribute the unchanged compiler metadata under our package namespace.
    # The versioned runtime tool name is identical to the tested platform recipe.
    package = dict(name='TerrainTronics', maintainer='TerrainTronics', websiteURL='https://terraintronics.com', email='', help=dict(online=REPO + '/issues'),
      platforms=[dict(name='TerrainTronics Holt Castle', architecture='ch32', version=VERSION, category='Contributed', **asset(platform_archive), boards=[dict(name='Holt Castle (CH32V006)')], toolsDependencies=[dict(packager='TerrainTronics',name='riscv-none-embed-gcc',version='8.2.0'),dict(packager='TerrainTronics',name='tt-upload',version=VERSION)])],
      tools=[compiler, dict(name='tt-upload',version=VERSION,systems=[dict(host='arm64-apple-darwin', **asset(tool_archive))])])
    index = a.output / 'package_terraintronics_index.json'
    index.write_text(json.dumps(dict(packages=[package]), indent=2) + '\n')
    (a.output / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest() + '  ' + f.name + '\n' for f in (platform_archive, tool_archive, index)))
    print(a.output.resolve())
if __name__ == '__main__': main()
