import uvicorn


def main() -> None:
    uvicorn.run(
        "env_notes.app:app",
        host="127.0.0.1",
        port=9490,
        reload=False,
    )


if __name__ == "__main__":
    main()
