#unix time (s) from discord snowflake
def unix_time(snowflake: int) -> int:
    return ((snowflake >> 22) + 1420070400000) // 1000

#time difference (s) between two snowflakes
def time_diff(before: int, after: int) -> int:
    return unix_time(after) - unix_time(before)