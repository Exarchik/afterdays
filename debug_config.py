"""Optional developer configuration; visibility is UI-only, never game state."""
import configparser
from pathlib import Path

def read_test_mode(path=None):
    config=configparser.ConfigParser()
    try:
        config.read(Path(path) if path is not None else Path(__file__).resolve().parent/'config.ini',encoding='utf-8-sig')
        return config.getboolean('debug','testmode',fallback=False)
    except (OSError,ValueError,configparser.Error):
        return False

TEST_MODE=read_test_mode()

class MapVisibility:
    show_full_map=False

    def map_revealed(self,x,y):
        """Визначає видимість клітинки з урахуванням тестового режиму."""
        return (TEST_MODE and self.show_full_map) or self.game.revealed(x,y)

    def map_city_known(self,index):
        """Визначає, чи слід показувати місто на карті."""
        return (TEST_MODE and self.show_full_map) or index in self.game.known_cities

    def toggle_test_map(self):
        """Перемикає повне відкриття карти у тестовому режимі."""
        if not TEST_MODE:return
        self.show_full_map=not self.show_full_map
        self.refresh()
