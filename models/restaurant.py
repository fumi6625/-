from dataclasses import dataclass, field


@dataclass
class Restaurant:
    name: str = ""           # 店名
    station: str = ""        # 最寄駅
    address: str = ""        # 住所
    genre: str = ""          # 食べ物のジャンル
    has_course: str = ""     # コース料理の有無（有/無/不明）
    all_you_drink: str = ""  # 飲み放題の有無（有/無/不明）
    seats: int = 0           # 席数
    private_room: str = ""   # 個室の有無（有/無/不明）
    budget: int = 0          # 大体の予算（円）
    url: str = ""            # お店へのリンク
    source: str = ""         # データソース（tabelog / hotpepper）

    def to_row(self) -> list:
        """Excelの1行分のデータをリストで返す"""
        return [
            self.name,
            self.station,
            self.address,
            self.genre,
            self.has_course,
            self.all_you_drink,
            self.seats if self.seats > 0 else "",
            self.private_room,
            self.budget if self.budget > 0 else "",
            self.url,
        ]
