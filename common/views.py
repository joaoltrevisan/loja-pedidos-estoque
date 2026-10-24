class PrivateResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code >= 400 and isinstance(response.data, dict):
            response.data.setdefault("errors", None)
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        return response
