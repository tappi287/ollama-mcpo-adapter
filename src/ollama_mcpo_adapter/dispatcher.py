import httpx
from typing import Dict, Any

def dispatch_tool_call(url: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches a tool call to the specified URL with the given parameters.

    :param url: The URL to send the tool call to.
    :param parameters: The parameters to include in the tool call.
    :return: The JSON response from the tool call or an error message.
    """
    try:
        response = httpx.post(url, json=parameters)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": str(e)}
    except httpx.RequestError as e:
        return {"error": str(e)}