# import numpy as np

# # Dictionary to store previous positions of faces (key: name, value: center position)
# previous_positions = {}

# def check_liveliness(name, current_box):
#     """
#     Check if a person is live by detecting movement in their bounding box.
#     Returns True if live, False otherwise.
#     """
#     x1, y1, x2, y2 = current_box
#     current_center = ((x1 + x2) // 2, (y1 + y2) // 2)  # Center of current bounding box

#     if name not in previous_positions:
#         # First detection of this person, store position and return False (need more frames)
#         previous_positions[name] = current_center
#         return False

#     # Calculate movement (Euclidean distance between centers)
#     prev_center = previous_positions[name]
#     movement = np.sqrt((current_center[0] - prev_center[0])**2 + (current_center[1] - prev_center[1])**2)

#     # Update previous position
#     previous_positions[name] = current_center

#     # Threshold for movement (adjust as needed)
#     MOVEMENT_THRESHOLD = 20  # Pixels
#     return movement > MOVEMENT_THRESHOLD


import numpy as np
from datetime import datetime, timedelta

# Dictionary to store previous positions and timestamps (key: name, value: (center position, timestamp))
previous_positions = {}

def reset_liveliness():
    """
    Reset the previous positions dictionary at the start of a new session.
    """
    global previous_positions
    previous_positions.clear()
    print("[+] Liveliness tracking reset.")

def check_liveliness(name, current_box):
    """
    Check if a person is live by detecting movement in their bounding box.
    Returns True if live, False otherwise.
    """
    x1, y1, x2, y2 = current_box
    current_center = ((x1 + x2) // 2, (y1 + y2) // 2)  # Center of current bounding box
    current_time = datetime.now()

    if name not in previous_positions:
        # First detection of this person, store position and return False (need more frames)
        previous_positions[name] = (current_center, current_time)
        return False

    # Get previous position and timestamp
    prev_center, prev_time = previous_positions[name]

    # Check if the previous position is too old (e.g., > 5 seconds)
    time_diff = (current_time - prev_time).total_seconds()
    if time_diff > 5:
        # Position is too old, treat this as a new detection
        previous_positions[name] = (current_center, current_time)
        return False

    # Calculate movement (Euclidean distance between centers)
    movement = np.sqrt((current_center[0] - prev_center[0])**2 + (current_center[1] - prev_center[1])**2)

    # Update previous position and timestamp
    previous_positions[name] = (current_center, current_time)

    # Threshold for movement (adjust as needed)
    MOVEMENT_THRESHOLD = 20  # Pixels
    return movement > MOVEMENT_THRESHOLD