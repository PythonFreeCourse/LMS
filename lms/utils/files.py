LANGUAGE_EXTENSIONS_TO_NAMES = {
    'bat': 'batch',
    'css': 'css',
    'h': 'c',
    'htm': 'html',
    'html': 'html',
    'js': 'javascript',
    'md': 'markup',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'py': 'python',
    'rb': 'ruby',
    'sh': 'bash',
    'sql': 'sql',
    'tex': 'latex',
    'yml': 'yaml',
}

ALLOWED_EXTENSIONS = set(LANGUAGE_EXTENSIONS_TO_NAMES)

ALLOWED_IMAGES_EXTENSIONS = {'png', 'jpeg', 'jpg', 'svg', 'tiff', 'bmp', 'ico'}


def get_language_name_by_extension(ext: str) -> str:
    return LANGUAGE_EXTENSIONS_TO_NAMES.get(ext, ext)
