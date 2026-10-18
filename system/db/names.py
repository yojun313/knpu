"""Application database names shared by all services and maintenance tools."""

DATABASE_PREFIX = "knpu-"
DATABASE_NAMES = {
    service: DATABASE_PREFIX + service
    for service in (
        "systems",
        "manager",
        "crawler",
        "homepage",
        "network",
        "kemkim",
        "statistics",
        "whisper",
        "admin",
        "mcdm",
    )
}


def database_name(name: str) -> str:
    """Resolve an application database name, preserving an existing prefix."""
    return name if name.startswith(DATABASE_PREFIX) else DATABASE_PREFIX + name
