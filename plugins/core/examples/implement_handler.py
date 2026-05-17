"""Example: implementing a custom handler using HandlerInterface."""

from pdf_autofiller_core import HandlerInterface, HandlerRequest, HandlerResponse


class MyHandler(HandlerInterface):
    def handle(self, request: HandlerRequest) -> HandlerResponse:
        # Custom processing logic here
        result = {"processed": True, "input": request.payload}
        return HandlerResponse(success=True, data=result)


if __name__ == "__main__":
    handler = MyHandler()
    request = HandlerRequest(payload={"field": "value"})
    response = handler.handle(request)
    print(response.data)
