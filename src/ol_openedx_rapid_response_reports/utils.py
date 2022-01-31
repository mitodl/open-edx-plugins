def get_display_name_from_usage_key(key, course):
    """
    Returns problem display name from given block UsageKey.
    Args:
        key (UsageKey) : Usage key of block
    Returns:
        String : Returns the display name of block if exists else 'Deleted'.
    """
    block = course.get_child(key)
    if block:
        return block.display_name
    else:
        return "Deleted"
