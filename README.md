# Bot Jacks - Telegram Bot

## Datos sensibles (.env)

Los datos sensibles ya estan en `.env`. **Nunca subas `.env` a GitHub**, esta en `.gitignore`.

Si clonas el repo en otro lado, copia `.env.example` a `.env` y rellena tus valores.

## Ejecutar con Docker (Ubuntu)

1. Instalar Docker y Docker Compose:
```bash
sudo apt update
sudo apt install docker.io docker-compose
```

2. Clonar o copiar el proyecto y entrar:
```bash
cd bot-jacks
```

3. Crear `.env` si no existe (usando `.env.example` como base).

4. Construir y levantar:
```bash
docker-compose up --build -d
```

5. Ver logs:
```bash
docker-compose logs -f
```

6. Detener:
```bash
docker-compose down
```

## Bugs corregidos

1. **SQL Injection** en `/comprar`: el `DELETE` usaba f-string directamente con los IDs. Ahora usa placeholders `?`.
2. **Transacciones atómicas** en `/comprar`: si fallaba algo entre borrar stock, descontar créditos e insertar historial, quedaba inconsistente. Ahora hay `BEGIN / ROLLBACK / COMMIT`.
3. **Compatibilidad Linux/Docker**: se eliminó codigo de event loop que solo funcionaba en Windows.
4. **Concurrencia SQLite**: se activo `PRAGMA journal_mode=WAL` para reducir bloqueos.
5. **Variables hardcodeadas**: token, admin IDs, grupo de logs, canal y owner ahora leen de `.env`.

## Dependencias

Instalar manualmente (si no usas Docker):
```bash
pip install -r requirements.txt
```

## Advertencias

- SQLite con `check_same_thread=False` funciona para cargas bajas/medianas. Si el bot crece mucho, migra a PostgreSQL/MySQL.
- El limite de Telegram para mensajes de texto es 4096 caracteres. El bot corta en 4000, lo cual es seguro.
