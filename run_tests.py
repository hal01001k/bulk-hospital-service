import sys
sys.modules['_asyncio'] = None
import pytest
if __name__ == '__main__':
    sys.exit(pytest.main())
