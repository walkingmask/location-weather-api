from enum import Enum
import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO
import math
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Union

from fastapi import FastAPI
from fastapi.logger import logger
from PIL import Image
from PIL.Image import Image as PILImage
from pydantic import BaseModel
import requests

JST = timezone(timedelta(hours=+9), 'JST')


class Location(BaseModel):
    """
    緯度経度を格納するデータクラス
    """
    lat: float
    lon: float


class TilePosition(BaseModel):
    """
    タイル座標とタイル画像内ピクセル座標を格納するデータクラス
    """
    location: Location
    zoom: int = 5
    x: Optional[float]
    y: Optional[float]
    tile_x: Optional[int]
    tile_y: Optional[int]
    pixel_x: Optional[int]
    pixel_y: Optional[int]

    def __init__(self, **data):
        """
        緯度経度を受け取って、タイル座標とタイル画像内ピクセル座標に変換する
        """
        super().__init__(**data)
        lat_rad = math.radians(self.location.lat)
        n = 2.0 ** self.zoom
        self.x = (self.location.lon + 180.0) / 360.0 * n
        self.y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        self.tile_x = int(self.x)
        self.tile_y = int(self.y)
        self.pixel_x = int((self.x - self.tile_x) * 256)
        self.pixel_y = int((self.y - self.tile_y) * 256)


"""
画像キャッシュの型定義

{
    (タイル座標 x, タイル座標 y): {
        "timestamp": タイムスタンプ (str),
        "image": 画像オブジェクト (PIL.Image),
    },
}
"""
ImageCache = Dict[
    Tuple[int, int], Dict[
        str, Union[str, PILImage],
    ],
]


class LocationWeatherForecast:
    """
    気象庁からの天気予報画像の取得とキャッシュ、それを使った地点天気予報を提供する
    """
    def __init__(self):
        self.cache: ImageCache = {}

    @staticmethod
    def get_timestamps(now: datetime.datetime) -> Tuple[str, str]:
        """
        与えられた datetime.datetime を使って、wdist の URL を構築するのに必要な、
        観測時刻と予報時刻を生成して返す。生成ルールは以下の通り。

        1. 現在時刻 (JST) が 00, 01, 02 時なら 00 時に丸める
        2. 現在時刻 (JST) が 03, 04, 05 時なら 03 時に丸める
        3. 現在時刻 (JST) が 06, 07, 08 時なら 06 時に丸める
        4. 他も同様
        5. 現在時刻が 06 時 (JST) 以前なら前日の 17:00 (JST) = 前日の 08:00 (UTC)
        6. 現在時刻が 12 時 (JST) 以前なら当日の 05:00 (JST) = 前日の 20:00 (UTC)
        7. 現在時刻が 18 時 (JST) 以前なら当日の 11:00 (JST) = 当日の 02:00 (UTC)
        8. 現在時刻が 19 時 (JST) 以降なら当日の 17:00 (JST) = 当日の 08:00 (UTC)
        9. 現在時刻の UTC を取得し、予報時刻とする
        """
        forecast_hour = [
            0, 0, 0,
            3, 3, 3,
            6, 6, 6,
            9, 9, 9,
            12, 12, 12,
            15, 15, 15,
            18, 18, 18,
            21, 21, 21,
        ][now.hour]
        if forecast_hour <= 6:
            observation_date = (now - timedelta(days=1)).date()
            observation_timestamp = \
                observation_date.strftime("%Y%m%d080000")
        elif forecast_hour <= 12:
            observation_date = (now - timedelta(days=1)).date()
            observation_timestamp = \
                observation_date.strftime("%Y%m%d200000")
        elif forecast_hour <= 18:
            observation_date = now.date()
            observation_timestamp = \
                observation_date.strftime("%Y%m%d020000")
        else:
            observation_date = now.date()
            observation_timestamp = \
                observation_date.strftime("%Y%m%d080000")
        forecast_datetime = datetime.datetime(
            now.year,
            now.month,
            now.day,
            forecast_hour,
            0,
        )
        forecast_datetime_utc = forecast_datetime - timedelta(hours=9)
        forecast_timestamp = forecast_datetime_utc.strftime("%Y%m%d%H%M%S")
        return observation_timestamp, forecast_timestamp

    @staticmethod
    def get_weather_forecast_image_url(
        observation_timestamp: str,
        forecast_timestamp: str,
        tile_position: TilePosition,
    ) -> str:
        """
        観測時刻と予報時刻、タイル座標から天気予報画像 URL を生成する
        """
        tail_part = "{}/none/{}/surf/wm/{}/{}/{}.png".format(
            observation_timestamp,
            forecast_timestamp,
            tile_position.zoom,
            tile_position.tile_x,
            tile_position.tile_y,
        )
        return f"https://www.jma.go.jp/bosai/jmatile/data/wdist/{tail_part}"

    @staticmethod
    def download_image(url) -> PILImage:
        """
        画像を PIL.Image としてダウンロードする
        """
        image = None
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                logger.info(f"successful image download from {url}")
            else:
                logger.warning(
                    f"unexpected response {response.status_code} from {url}"
                )
        except:
            logger.exception(f"failed to download image from {url}")
        return image

    def get_location_weather_forecast(
        self,
        location: Location,
    ) -> Dict[str, Union[str, Location, TilePosition]]:
        """
        気象庁の天気予報画像を用いて、緯度経度からその地点の天気予報を返す
        """
        tile_position = TilePosition(location=location)
        now = datetime.datetime.now(tz=JST)
        observation_timestamp, forecast_timestamp = self.get_timestamps(now)
        image_url = self.get_weather_forecast_image_url(
            observation_timestamp,
            forecast_timestamp,
            tile_position,
        )
        cache_key = (tile_position.tile_x, tile_position.tile_y)
        if (
            cache_key not in self.cache
            or
            self.cache[cache_key]["timestamp"] < forecast_timestamp
        ):
            logger.info("cache not found. try to download new image...")
            self.cache[cache_key] = {}
            self.cache[cache_key]["image"] = self.download_image(image_url)
            self.cache[cache_key]["timestamp"] = forecast_timestamp
        else:
            logger.info("cache found. use cache.")
        forecast_image = self.cache[cache_key]["image"]
        if forecast_image and forecast_image.mode == "P":
            pixel_value = forecast_image.getpixel((
                tile_position.pixel_x,
                tile_position.pixel_y,
            ))
        else:
            pixel_value = 0
        weather = {
            0: "unkown",
            1: "sunny",
            2: "cloudy",
            3: "rainy",
            4: "sleet",
            5: "snow",
        }[pixel_value]
        return {
            "weather": weather,
            "location": location,
            "tile_position": tile_position,
            "now": now.strftime("%Y/%m/%d %H:%M:%S"),
            "utc": (now - timedelta(hours=9)).strftime("%Y/%m/%d %H:%M:%S"),
            "observation_timestamp": observation_timestamp,
            "forecast_timestamp": forecast_timestamp,
            "image_url": image_url,
        }


class LocationRainfall:
    """
    気象庁からの降雨画像の取得とキャッシュ、それを使った地点降雨量を提供する
    """
    def __init__(self):
        self.cache: ImageCache = {}

    @staticmethod
    def get_timestamps(now: datetime.datetime) -> Tuple[str, str]:
        """
        与えられた datetime.datetime nowc の URL を構築するのに必要な、
        観測時刻と予報時刻を生成して返す。生成ルールは以下の通り。

        現在時刻 (JST) の分を 5 の倍数に丸め、秒以降を 0 にして UTC に変換したものを
        観測時刻と予報時刻とする
        （例：2021/08/01 12:07:21 (JST) -> 2021/08/01 03:05:00 (UTC)）
        """
        round_minute = 5 * int(now.minute / 5)
        round_now = datetime.datetime(
            now.year,
            now.month,
            now.day,
            now.hour,
            round_minute,
            0,
        )
        utc = round_now - timedelta(hours=9)
        timestamp = utc.strftime("%Y%m%d%H%M%S")
        return timestamp, timestamp

    @staticmethod
    def get_rainfall_image_url(
        observation_timestamp: str,
        forecast_timestamp: str,
        tile_position: TilePosition,
    ) -> str:
        """
        観測時刻と予報時刻、タイル座標から天気予報画像 URL を生成する
        """
        tail_part = "{}/none/{}/surf/hrpns/{}/{}/{}.png".format(
            observation_timestamp,
            forecast_timestamp,
            tile_position.zoom,
            tile_position.tile_x,
            tile_position.tile_y,
        )
        return f"https://www.jma.go.jp/bosai/jmatile/data/nowc/{tail_part}"

    @staticmethod
    def download_image(url) -> PILImage:
        """
        画像を PIL.Image としてダウンロードする
        """
        image = None
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                logger.info(f"successful image download from {url}")
            else:
                logger.warning(
                    f"unexpected response {response.status_code} from {url}"
                )
        except:
            logger.exception(f"failed to download image from {url}")
        return image

    def get_location_rainfall(
        self,
        location: Location,
    ) -> Dict[str, Union[str, Location, TilePosition]]:
        """
        気象庁の降雨画像を用いて、緯度経度からその地点の降雨量を返す
        """
        tile_position = TilePosition(location=location, zoom=9)
        now = datetime.datetime.now(tz=JST)
        observation_timestamp, forecast_timestamp = self.get_timestamps(now)
        image_url = self.get_rainfall_image_url(
            observation_timestamp,
            forecast_timestamp,
            tile_position,
        )
        cache_key = (tile_position.tile_x, tile_position.tile_y)
        if (
            cache_key not in self.cache
            or
            self.cache[cache_key]["timestamp"] < forecast_timestamp
        ):
            logger.info("cache not found. try to download new image...")
            self.cache[cache_key] = {}
            self.cache[cache_key]["image"] = self.download_image(image_url)
            self.cache[cache_key]["timestamp"] = forecast_timestamp
        else:
            logger.info("cache found. use cache.")
        rainfall_image = self.cache[cache_key]["image"]
        if rainfall_image and rainfall_image.mode == "P":
            pixel_value = rainfall_image.getpixel((
                tile_position.pixel_x,
                tile_position.pixel_y,
            ))
        else:
            pixel_value = 0
        rainfall = {
            0: 0,
            1: 0,
            2: 1,
            3: 5,
            4: 10,
            5: 20,
            6: 30,
            7: 50,
            8: 80,
            9: 100,
        }[pixel_value]
        return {
            "rainfall": rainfall,
            "location": location,
            "tile_position": tile_position,
            "now": now.strftime("%Y/%m/%d %H:%M:%S"),
            "utc": (now - timedelta(hours=9)).strftime("%Y/%m/%d %H:%M:%S"),
            "observation_timestamp": observation_timestamp,
            "forecast_timestamp": forecast_timestamp,
            "image_url": image_url,
        }


app = FastAPI(
    title="Location Weather API",
    description=(
        "Get the latest weather info for a certain location in"
        " Japan using the weather forecast and rainfall image of"
        " the Japan Meteorological Agency."
    ),
    version="0.0.1",
)
location_weather = LocationWeatherForecast()
location_rainfall = LocationRainfall()


class WeatherEnum(str, Enum):
    """
    地点天気予報レスポンスに含む天気種別の定義
    """
    unkown = "unkown"
    sunny = "sunny"
    cloudy = "cloudy"
    rainy = "rainy"
    sleet = "sleet"
    snow = "snow"


class LocationWeatherForecastResponse(BaseModel):
    """
    地点天気予報レスポンス定義
    """
    weather: WeatherEnum
    location: Location
    tile_position: TilePosition
    now: str
    utc: str
    observation_timestamp: str
    forecast_timestamp: str
    image_url: str


@app.post(
    "/location_weather_forecast",
    response_model=LocationWeatherForecastResponse,
)
async def get_location_weather_forecast(location: Location):
    """
    気象庁の天気予報画像を用いて、緯度経度からその地点の天気予報を返す API
    """
    return location_weather.get_location_weather_forecast(location)


class RainfallEnum(int, Enum):
    """
    地点降雨量レスポンスに含む降水量の定義
    """
    zero = 0
    one = 1
    five = 5
    ten = 10
    twenty = 20
    thirty = 30
    fifty = 50
    eighty = 80
    hundred = 100


class LocationRainfallResponse(BaseModel):
    """
    地点降雨量レスポンス定義
    """
    rainfall: RainfallEnum
    location: Location
    tile_position: TilePosition
    now: str
    utc: str
    observation_timestamp: str
    forecast_timestamp: str
    image_url: str


@app.post(
    "/location_rainfall",
    response_model=LocationRainfallResponse,
)
async def get_location_rainfall(location: Location):
    """
    気象庁の天気予報画像を用いて、緯度経度からその地点の降雨量を返す API
    """
    return location_rainfall.get_location_rainfall(location)


class HealthStatus(BaseModel):
    """
    API サーバーの健康状態の定義データクラス
    """
    status: bool


@app.get("/healthcheck", response_model=HealthStatus)
async def healthcheck():
    """
    API サーバーの健康状態を取得する API
    """
    return {"status": True}
