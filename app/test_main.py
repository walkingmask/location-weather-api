import datetime
from pathlib import Path
import sys
import unittest
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from PIL.Image import Image as PILImage

HERE = Path(__file__).resolve().parent

sys.path.append(str(HERE))

from main import JST
from main import Location
from main import LocationRainfall
from main import LocationRainfallResponse
from main import LocationWeatherForecastResponse
from main import LocationWeatherForecast
from main import RainfallEnum
from main import TilePosition
from main import WeatherEnum
from main import app

EXAMPLE_IMAGES_DIR = HERE / "example_images"


class TestLocation(TestCase):

    def test___init__(self):
        location = Location(lat=26.206998, lon=127.65174)
        self.assertEqual(location.lat, 26.206998)
        self.assertEqual(location.lon, 127.65174)


class TestTilePosition(TestCase):

    def test___init__(self):
        location = Location(lat=26.206998, lon=127.65174)
        tile_position = TilePosition(location=location)
        self.assertEqual(tile_position.zoom, 5)
        self.assertEqual(tile_position.x, 27.346821333333335)
        self.assertEqual(tile_position.y, 13.584736664484332)
        self.assertEqual(tile_position.tile_x, 27)
        self.assertEqual(tile_position.tile_y, 13)
        self.assertEqual(tile_position.pixel_x, 88)
        self.assertEqual(tile_position.pixel_y, 149)

        tile_position = TilePosition(location=location, zoom=4)
        self.assertEqual(tile_position.zoom, 4)
        self.assertEqual(tile_position.tile_x, 13)
        self.assertEqual(tile_position.tile_y, 6)


class TestLocationWeatherForecast(TestCase):

    def test___init__(self):
        location_weather_forecast = LocationWeatherForecast()
        self.assertDictEqual(location_weather_forecast.cache, {})

    def test_get_timestamps(self):
        now = datetime.datetime(2021, 8, 1, 5, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731080000")
        self.assertEqual(timestamps[1], "20210731180000")

        now = datetime.datetime(2021, 8, 1, 6, 0)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731080000")
        self.assertEqual(timestamps[1], "20210731210000")

        now = datetime.datetime(2021, 8, 1, 6, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731080000")
        self.assertEqual(timestamps[1], "20210731210000")

        now = datetime.datetime(2021, 8, 1, 7, 0)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731080000")
        self.assertEqual(timestamps[1], "20210731210000")

        now = datetime.datetime(2021, 8, 1, 11, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731200000")
        self.assertEqual(timestamps[1], "20210801000000")

        now = datetime.datetime(2021, 8, 1, 12, 0)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731200000")
        self.assertEqual(timestamps[1], "20210801030000")

        now = datetime.datetime(2021, 8, 1, 12, 59, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731200000")
        self.assertEqual(timestamps[1], "20210801030000")

        now = datetime.datetime(2021, 8, 1, 13, 0)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731200000")
        self.assertEqual(timestamps[1], "20210801030000")

        now = datetime.datetime(2021, 8, 1, 17, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801020000")
        self.assertEqual(timestamps[1], "20210801060000")

        now = datetime.datetime(2021, 8, 1, 18, 00)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801020000")
        self.assertEqual(timestamps[1], "20210801090000")

        now = datetime.datetime(2021, 8, 1, 18, 59, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801020000")
        self.assertEqual(timestamps[1], "20210801090000")

        now = datetime.datetime(2021, 8, 1, 19, 0)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801020000")
        self.assertEqual(timestamps[1], "20210801090000")

        now = datetime.datetime(2021, 8, 1, 23, 59, 59)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801080000")
        self.assertEqual(timestamps[1], "20210801120000")

        now = datetime.datetime(2021, 8, 2, 0, 0)
        timestamps = LocationWeatherForecast.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801080000")
        self.assertEqual(timestamps[1], "20210801150000")

    def test_get_weather_forecast_image_url(self):
        location = Location(lat=26.206998, lon=127.65174)
        tile_position = TilePosition(location=location)
        image_url = LocationWeatherForecast.get_weather_forecast_image_url(
            "20210731080000",
            "20210731180000",
            tile_position,
        )
        self.assertEqual(
            image_url,
            "https://www.jma.go.jp/bosai/jmatile/data/wdist/20210731080000/none/20210731180000/surf/wm/5/27/13.png",
        )

        location = Location(lat=26.206998, lon=127.65174)
        tile_position = TilePosition(location=location, zoom=4)
        image_url = LocationWeatherForecast.get_weather_forecast_image_url(
            "20210801080000",
            "20210801150000",
            tile_position,
        )
        self.assertEqual(
            image_url,
            "https://www.jma.go.jp/bosai/jmatile/data/wdist/20210801080000/none/20210801150000/surf/wm/4/13/6.png",
        )

    @unittest.skip("To reduce the load on the jma server and test time")
    def test_download_image(self):
        location = Location(lat=26.206998, lon=127.65174)
        tile_position = TilePosition(location=location)
        timestamps = LocationWeatherForecast.get_timestamps(datetime.datetime.now(tz=JST))
        image_url = LocationWeatherForecast.get_weather_forecast_image_url(*timestamps, tile_position)
        with self.assertLogs("fastapi", level="INFO") as cm:
            image = LocationWeatherForecast.download_image(image_url)
            self.assertTrue("successful image download from" in cm.output[0])
        self.assertIsInstance(image, PILImage)

        image_url = "https://www.jma.go.jp/bosai/jmatile/data/wdist/21000801080000/none/21000801080000/surf/wm/4/13/6.png"
        with self.assertLogs("fastapi", level="WARNING") as cm:
            image = LocationWeatherForecast.download_image(image_url)
            self.assertTrue("unexpected response" in cm.output[0])

        image_url = "THIS_IS_INVALID_URL"
        with self.assertLogs("fastapi", level="ERROR") as cm:
            image = LocationWeatherForecast.download_image(image_url)
            self.assertTrue("failed to download image from" in cm.output[0])

    @patch.object(LocationWeatherForecast, "download_image")
    def test_get_location_weather_forecast(self, mock_download_image):
        location_weather_forecast = LocationWeatherForecast()
        location = Location(lat=26.206998, lon=127.65174)

        with self.assertLogs("fastapi", level="INFO") as cm:
            with Image.open(str(EXAMPLE_IMAGES_DIR / "13.png")) as example_image:
                mock_download_image.return_value = example_image
                info = location_weather_forecast.get_location_weather_forecast(location)
                self.assertIsInstance(info, dict)
                self.assertEqual(info["weather"], "cloudy")
                self.assertTrue("cache not found." in cm.output[0])

        with self.assertLogs("fastapi", level="INFO") as cm:
            with Image.open(str(EXAMPLE_IMAGES_DIR / "13.png")) as example_image:
                mock_download_image.return_value = example_image
                info = location_weather_forecast.get_location_weather_forecast(location)
                self.assertTrue("cache found." in cm.output[0])

        location = Location(lat=0, lon=0)
        with Image.open(str(EXAMPLE_IMAGES_DIR / "0.png")) as example_image:
            mock_download_image.return_value = example_image
            info = location_weather_forecast.get_location_weather_forecast(location)
            self.assertEqual(info["weather"], "unkown")

        location = Location(lat=100, lon=100)
        mock_download_image.return_value = None
        info = location_weather_forecast.get_location_weather_forecast(location)
        self.assertEqual(info["weather"], "unkown")


class TestLocationRainfall(TestCase):

    def test___init__(self):
        location_rainfall = LocationRainfall()
        self.assertDictEqual(location_rainfall.cache, {})

    def test_get_timestamps(self):
        now = datetime.datetime(2021, 8, 1, 0, 0)
        timestamps = LocationRainfall.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210731150000")
        self.assertEqual(timestamps[1], "20210731150000")

        now = datetime.datetime(2021, 8, 1, 12, 59)
        timestamps = LocationRainfall.get_timestamps(now)
        self.assertEqual(timestamps[0], "20210801035500")
        self.assertEqual(timestamps[1], "20210801035500")

    def test_get_rainfall_image_url(self):
        location = Location(lat=33.903307, lon=130.933741)
        tile_position = TilePosition(location=location, zoom=9)
        image_url = LocationRainfall.get_rainfall_image_url(
            "20210731150000",
            "20210731150000",
            tile_position,
        )
        self.assertEqual(
            image_url,
            "https://www.jma.go.jp/bosai/jmatile/data/nowc/20210731150000/none/20210731150000/surf/hrpns/9/442/204.png",
        )

    @unittest.skip("To reduce the load on the jma server and test time")
    def test_download_image(self):
        location = Location(lat=33.903307, lon=130.933741)
        tile_position = TilePosition(location=location, zoom=9)
        timestamps = LocationRainfall.get_timestamps(datetime.datetime.now(tz=JST))
        image_url = LocationRainfall.get_rainfall_image_url(*timestamps, tile_position)
        with self.assertLogs("fastapi", level="INFO") as cm:
            image = LocationRainfall.download_image(image_url)
            self.assertTrue("successful image download from" in cm.output[0])
        self.assertIsInstance(image, PILImage)

        image_url = "https://www.jma.go.jp/bosai/jmatile/data/nowc/21000731150000/none/21000731150000/surf/hrpns/9/442/204.png"
        with self.assertLogs("fastapi", level="WARNING") as cm:
            image = LocationRainfall.download_image(image_url)
            self.assertTrue("unexpected response" in cm.output[0])

        image_url = "THIS_IS_INVALID_URL"
        with self.assertLogs("fastapi", level="ERROR") as cm:
            image = LocationRainfall.download_image(image_url)
            self.assertTrue("failed to download image from" in cm.output[0])

    @patch.object(LocationRainfall, "download_image")
    def test_get_location_weather_forecast(self, mock_download_image):
        location_rainfall = LocationRainfall()
        location = Location(lat=33.903307, lon=130.933741)

        with self.assertLogs("fastapi", level="INFO") as cm:
            with Image.open(str(EXAMPLE_IMAGES_DIR / "204.png")) as example_image:
                mock_download_image.return_value = example_image
                result = location_rainfall.get_location_rainfall(location)
                self.assertIsInstance(result, dict)
                self.assertEqual(result["rainfall"], 80)
                self.assertTrue("cache not found." in cm.output[0])

        with self.assertLogs("fastapi", level="INFO") as cm:
            with Image.open(str(EXAMPLE_IMAGES_DIR / "13.png")) as example_image:
                mock_download_image.return_value = example_image
                result = location_rainfall.get_location_rainfall(location)
                self.assertTrue("cache found." in cm.output[0])

        location = Location(lat=0, lon=0)
        with Image.open(str(EXAMPLE_IMAGES_DIR / "0.png")) as example_image:
            mock_download_image.return_value = example_image
            result = location_rainfall.get_location_rainfall(location)
            self.assertEqual(result["rainfall"], 0)

        location = Location(lat=100, lon=100)
        mock_download_image.return_value = None
        result = location_rainfall.get_location_rainfall(location)
        self.assertEqual(result["rainfall"], 0)


class TestWeatherEnum(TestCase):

    def test___init__(self):
        weather = WeatherEnum("sunny")
        self.assertEqual(weather.value, "sunny")

        with self.assertRaises(ValueError):
            weather = WeatherEnum("NOT_DEFINED")

        with self.assertRaises(ValueError):
            weather = WeatherEnum(0)


class TestLocationWeatherForecastResponse(TestCase):

    def test___init__(self):
        location = Location(lat=26.206998, lon=127.65174)
        tile_position = TilePosition(location=location)
        response = LocationWeatherForecastResponse(
            weather="unkown",
            location=location,
            tile_position=tile_position,
            now="2021/08/01 12:00:00",
            utc="2021/08/01 03:00:00",
            observation_timestamp="20210731200000",
            forecast_timestamp="20210801030000",
            image_url="https://www.jma.go.jp/bosai/jmatile/data/wdist/20210731200000/none/20210801030000/surf/wm/5/27/13.png",
        )
        self.assertEqual(response.weather, "unkown")
        self.assertEqual(response.location, location)
        self.assertEqual(response.tile_position, tile_position)
        self.assertEqual(response.now, "2021/08/01 12:00:00")
        self.assertEqual(response.utc, "2021/08/01 03:00:00")
        self.assertEqual(response.observation_timestamp, "20210731200000")
        self.assertEqual(response.forecast_timestamp, "20210801030000")
        self.assertEqual(response.image_url, "https://www.jma.go.jp/bosai/jmatile/data/wdist/20210731200000/none/20210801030000/surf/wm/5/27/13.png")


class TestRainfallEnum(TestCase):

    def test___init__(self):
        rainfall = RainfallEnum(0)
        self.assertEqual(rainfall.value, 0)

        with self.assertRaises(ValueError):
            rainfall = RainfallEnum(3)

        with self.assertRaises(ValueError):
            rainfall = RainfallEnum("10")


class TestLocationRainfallResponse(TestCase):

    def test___init__(self):
        location = Location(lat=33.903307, lon=130.933741)
        tile_position = TilePosition(location=location, zoom=9)
        response = LocationRainfallResponse(
            rainfall=80,
            location=location,
            tile_position=tile_position,
            now="2021/08/01 12:00:00",
            utc="2021/08/01 03:00:00",
            observation_timestamp="20210731030000",
            forecast_timestamp="20210731030000",
            image_url="https://www.jma.go.jp/bosai/jmatile/data/nowc/20210731030000/none/20210731030000/surf/hrpns/9/442/204.png",
        )
        self.assertEqual(response.rainfall, 80)
        self.assertEqual(response.location, location)
        self.assertEqual(response.tile_position, tile_position)
        self.assertEqual(response.now, "2021/08/01 12:00:00")
        self.assertEqual(response.utc, "2021/08/01 03:00:00")
        self.assertEqual(response.observation_timestamp, "20210731030000")
        self.assertEqual(response.forecast_timestamp, "20210731030000")
        self.assertEqual(response.image_url, "https://www.jma.go.jp/bosai/jmatile/data/nowc/20210731030000/none/20210731030000/surf/hrpns/9/442/204.png")


class TestApp(TestCase):

    @patch.object(LocationWeatherForecast, "download_image")
    def test_location_weather_forecast(self, mock_download_image):
        with Image.open(str(EXAMPLE_IMAGES_DIR / "13.png")) as example_image:
            mock_download_image.return_value = example_image
            client = TestClient(app)
            response = client.post(
                "/location_weather_forecast",
                json={"lat": 26.206998, "lon": 127.65174},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["weather"], "cloudy")

    @patch.object(LocationRainfall, "download_image")
    def test_location_weather_forecast(self, mock_download_image):
        with Image.open(str(EXAMPLE_IMAGES_DIR / "204.png")) as example_image:
            mock_download_image.return_value = example_image
            client = TestClient(app)
            response = client.post(
                "/location_rainfall",
                json={"lat": 33.903307, "lon": 130.933741},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["rainfall"], 80)

    def test_healthcheck(self):
        client = TestClient(app)
        response = client.get("/healthcheck")
        self.assertEqual(response.status_code, 200)
        assert response.json() == {"status": True}


if __name__ == "__main__":
    unittest.main()
