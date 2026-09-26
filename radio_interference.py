"""Cosmetic radio interference; uses no gameplay RNG or quest target mutations."""
import random
class Interference:
    def __init__(self,now,rng=None):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        self.rng=rng or random.Random();self.noisy=False;self.next=now+self.rng.uniform(7,13)
    def advance(self,now):
        """Просуває поточну анімацію або маршрут на наступний етап."""
        if now>=self.next:
            self.noisy=not self.noisy;self.next=now+self.rng.uniform(2,4) if self.noisy else now+self.rng.uniform(7,13)
        return self.noisy
    def trace(self,width,height):
        """Оновлює реакцію інтерфейсу на зміну спостережуваного значення."""
        return [v for x in range(8,width-8,4) for v in (x,self.rng.uniform(15,height-15))]
