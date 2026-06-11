import time


def retry_request(func, retries=5):
    """
    Retries a request function with exponential backoff.

    Usage:
        response = retry_request(
            lambda: session.post(url, ...)
        )

    Attempt 1 → 1s wait
    Attempt 2 → 2s wait
    Attempt 3 → 4s wait
    Attempt 4 → 8s wait
    Attempt 5 → 16s wait
    """

    last_exception = None

    for attempt in range(retries):

        try:

            print(
                f"[RETRY] Attempt {attempt + 1}/{retries}"
            )

            result = func()

            return result

        except Exception as e:

            last_exception = e

            print(
                f"[RETRY] Failed: {e}"
            )

            if attempt == retries - 1:
                break

            wait_time = 2 ** attempt

            print(
                f"[RETRY] Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise Exception(
        f"All {retries} attempts failed. "
        f"Last error: {last_exception}"
    )