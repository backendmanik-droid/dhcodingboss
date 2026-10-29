# =========================
# UTILITY FUNCTIONS
# =========================


def success_response(message, data=None, status_code=200):
    """Return a standard success response."""
    response = {'message': message}
    if data is not None:
        response['data'] = data
    return response


def error_response(message, errors=None):
    """Return a standard error response."""
    response = {'message': message}
    if errors is not None:
        response['errors'] = errors
    return response
