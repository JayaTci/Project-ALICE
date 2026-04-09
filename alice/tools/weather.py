import httpx
from alice.config import settings
from alice.tools.base import BaseTool, ToolResult

OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherTool(BaseTool):
    name = "get_weather"
    description = (
        "Get the current weather for Chester's location (Tagum City, Philippines by default) "
        "or any specified city. Returns temperature, conditions, humidity, and wind."
    )
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name. Defaults to configured location.",
            },
            "country_code": {
                "type": "string",
                "description": "ISO country code (e.g. 'PH', 'US'). Optional.",
            },
        },
        "required": [],
    }
    is_read_only = True

    async def execute(self, city: str = "", country_code: str = "", **_) -> ToolResult:
        api_key = settings.openweather_api_key
        if not api_key:
            return ToolResult(
                success=False, output="",
                error="OpenWeatherMap API key not configured. Set OPENWEATHER_API_KEY in .env."
            )

        location = city or settings.weather_city
        cc = country_code or settings.weather_country_code
        if cc:
            location = f"{location},{cc}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    OWM_URL,
                    params={"q": location, "appid": api_key, "units": "metric"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return ToolResult(success=False, output="", error=f"Weather API error: {exc.response.status_code}")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

        city_name = data.get("name", location)
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        conditions = data["weather"][0]["description"].capitalize()
        wind_speed = data["wind"]["speed"]

        output = (
            f"Weather in {city_name}:\n"
            f"  Conditions: {conditions}\n"
            f"  Temperature: {temp:.1f}°C (feels like {feels_like:.1f}°C)\n"
            f"  Humidity: {humidity}%\n"
            f"  Wind: {wind_speed} m/s"
        )
        return ToolResult(success=True, output=output)
