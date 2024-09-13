RESET="\033[0m"
VERBOSITY=0

def set_verbosity(level):
    global VERBOSITY
    VERBOSITY = level

def disp_color(r, g, b, *msg, **kwargs):
    print(color(r, g, b), end="")
    print(*msg, **kwargs)
    print(RESET, end="")

def color(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

def reset_style():
    print(RESET, end="")

def msg_debug(*msg):
    if VERBOSITY >= 3:
        disp_color(128, 128, 128, *msg)

def msg_system(*msg):
    if VERBOSITY >= 2:
        disp_color(128, 128, 128, *msg)

def set_ai_color():
    print(color(255, 128, 200), end="")

def set_user_color():
    print(color(128, 255, 200), end="")
