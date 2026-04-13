import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django."
        ) from exc

    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
