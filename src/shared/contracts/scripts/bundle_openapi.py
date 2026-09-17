"""Bundle this repository's local OpenAPI files without changing component refs.

Usage: python3 src/shared/contracts/scripts/bundle_openapi.py --output /tmp/openapi.yaml
Requires PyYAML. The generated file is an artifact, not an editable source.
"""
import argparse
from pathlib import Path
import yaml

ENTRY = Path(__file__).resolve().parents[1] / 'openapi.yaml'


def bundle(entry=ENTRY):
    entry = Path(entry).resolve()
    cache = {}

    def read(path):
        if path not in cache:
            cache[path] = yaml.safe_load(path.read_text())
        return cache[path]

    def walk(value, origin, stack=()):
        if isinstance(value, list):
            return [walk(item, origin, stack) for item in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            ref = value['$ref']
            filename, separator, fragment = ref.partition('#')
            target = (origin.parent / filename).resolve() if filename else origin
            if target == entry:
                return {key: ('#' + fragment if key == '$ref' else walk(item, origin, stack))
                        for key, item in value.items()}
            if not separator or not fragment.startswith('/'):
                raise ValueError(f'Expected local JSON pointer: {ref}')
            identity = (target, fragment)
            if identity in stack:
                raise ValueError(f'External reference cycle: {ref}')
            node = read(target)
            for part in fragment[1:].split('/'):
                node = node[part.replace('~1', '/').replace('~0', '~')]
            resolved = walk(node, target, (*stack, identity))
            if len(value) != 1:
                raise ValueError(f'External ref siblings require explicit support: {ref}')
            return resolved
        # Discriminator mappings are URI strings, not $ref objects.
        return {key: ('#' + item.split('#', 1)[1]
                      if isinstance(item, str) and item.startswith('../openapi.yaml#/')
                      else walk(item, origin, stack)) for key, item in value.items()}

    return walk(read(entry), entry)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(yaml.safe_dump(bundle(), allow_unicode=True, sort_keys=False, width=100))
    print(f'Bundled OpenAPI: {args.output}')
