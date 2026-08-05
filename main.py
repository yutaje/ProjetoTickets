from fastapi import FastAPI

app = FastAPI(title="FlowPulse API")


@app.get("/")
def home():
    return {"mensagem": "O backend do FlowPulse está oficialmente online, bro!"}