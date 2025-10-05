from app import app

# Vercel serverless function
def handler(request):
    return app(request.environ, lambda *args: None)
