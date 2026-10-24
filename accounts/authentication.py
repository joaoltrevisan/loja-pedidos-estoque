from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings


def token_user_id(token):
    user_id = token.get(api_settings.USER_ID_CLAIM)
    # Tokens emitidos pela biblioteca usam a PK como string. Evita coercoes
    # inesperadas pelo ORM e IDs invalidos ou fora do intervalo de bigint.
    if (
        not isinstance(user_id, str)
        or not user_id.isascii()
        or not user_id.isdecimal()
        or len(user_id) > 19
        or not 0 < int(user_id) <= 9223372036854775807
    ):
        raise InvalidToken("Identificacao de usuario invalida.")
    return user_id


class DatabaseJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        token_user_id(validated_token)
        # A biblioteca consulta o banco, verifica conta ativa e senha alterada.
        return super().get_user(validated_token)
