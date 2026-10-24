from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe
from django.views.defaults import page_not_found


@require_safe
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        # A sonda nao revela credenciais, endereco do banco ou detalhes da excecao.
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def not_found(request, exception):
    if request.path.startswith("/api/"):
        response = JsonResponse(
            {"code": "not_found", "detail": "Recurso nao encontrado.", "errors": None}, status=404
        )
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        return response
    return page_not_found(request, exception)
