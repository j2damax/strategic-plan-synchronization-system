"""LLM Caching Configuration.

Enables persistent caching for all LangChain LLM calls to reduce costs and latency.
"""

from pathlib import Path
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache


def setup_cache(cache_dir: str = ".cache") -> None:
    """Setup SQLite cache for all LangChain LLM calls.

    Args:
        cache_dir: Directory to store cache database (default: .cache)
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(exist_ok=True)

    cache_db = cache_path / "langchain_cache.db"

    # Set global LLM cache
    set_llm_cache(SQLiteCache(database_path=str(cache_db)))

    print(f"✅ LLM cache enabled: {cache_db}")


def clear_cache(cache_dir: str = ".cache") -> None:
    """Clear the LLM cache database.

    Args:
        cache_dir: Directory containing cache database
    """
    cache_db = Path(cache_dir) / "langchain_cache.db"

    if cache_db.exists():
        cache_db.unlink()
        print(f"✅ Cache cleared: {cache_db}")
    else:
        print("ℹ️ No cache to clear")
