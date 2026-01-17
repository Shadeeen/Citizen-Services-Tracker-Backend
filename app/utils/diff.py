def diff_lists(old: list, new: list):
    old_set = set(old or [])
    new_set = set(new or [])

    return {
        "added": list(new_set - old_set),
        "removed": list(old_set - new_set),
    }
