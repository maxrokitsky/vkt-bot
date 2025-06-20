import uvicorn
from webapp.app import app


if __name__ == "__main__":
    uvicorn.run(app)
