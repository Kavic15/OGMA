import time
import random

def delay(base_delay: float):
    """
    Delays execution for a time randomly varied by ±1 second from the base delay.

    Args:
        base_delay (float): The base delay in seconds.
    """
    variation = random.uniform(-0.5, 0.5)
    actual_delay = base_delay + variation
    actual_delay = max(0, actual_delay)  # Ensure delay is not negative
    print(f"Delaying for {actual_delay:.2f} seconds...")
    time.sleep(actual_delay)
    print("Delay complete.")
