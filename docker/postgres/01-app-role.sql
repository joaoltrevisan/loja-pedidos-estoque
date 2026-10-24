-- Executado uma unica vez pela imagem oficial, ao inicializar um volume vazio.
-- Variaveis lidas do ambiente; identificadores e senha sao escapados pelo psql.
\getenv app_user APP_DB_USER
\getenv app_password APP_DB_PASSWORD
\getenv app_database POSTGRES_DB
CREATE ROLE :"app_user" WITH LOGIN PASSWORD :'app_password' CREATEDB NOSUPERUSER NOCREATEROLE;
ALTER DATABASE :"app_database" OWNER TO :"app_user";
-- CREATEDB e exclusivo deste ambiente de desenvolvimento e testes.
