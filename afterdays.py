"""Windows/script entry point for Afterdays; gameplay lives in game.model."""
import sys

from i18n import t as tr


def main():
    try:
        from ui.application import launch
        launch()
    except ImportError as exc:
        if exc.name in ('tkinter', '_tkinter'):
            print(tr('afterdays.0210'))
        elif exc.name == 'PIL' or (exc.name or '').startswith('PIL.'):
            print('Потрібен Pillow для зображень мапи. Команда для PowerShell:')
            print(f'& "{sys.executable}" -m pip install Pillow')
        else:
            raise
        print(f'Python: {sys.executable}\nПричина: {exc}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
