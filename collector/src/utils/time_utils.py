from datetime import datetime, timezone

def get_utc_timestamp() -> str:
    """
    Get the current UTC timestamp in ISO format with timezone info.
    
    Returns:
        str: ISO formatted timestamp with timezone info (e.g., '2025-03-11T21:34:56.789012+00:00')
    """
    return datetime.now(timezone.utc).isoformat()

def format_timestamp(dt: datetime = None) -> str:
    """
    Format a datetime object as an ISO timestamp with timezone info.
    If no datetime is provided, the current UTC time is used.
    
    Args:
        dt (datetime, optional): The datetime to format. Defaults to None (current UTC time).
    
    Returns:
        str: ISO formatted timestamp with timezone info
    """
    if dt is None:
        return get_utc_timestamp()
        
    # Ensure the datetime has timezone info
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        
    return dt.isoformat() 