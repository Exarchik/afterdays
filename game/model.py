"""Explicit gameplay composition; systems cooperate in established dispatch order."""
from game.progression import ProgressionGame

from game.systems.adventure import AdventureMixin
from game.systems.economy import EconomyMixin
from game.systems.frontier import FrontierMixin
from game.systems.quests import QuestSystem
from game.systems.reputation import Reputation
from game.systems.border import Border
from game.systems.journey import Guides
from game.systems.contracts import ContractsMixin
from game.systems.expeditions import ExpeditionsMixin
from game.systems.scavenging import ScavengingMixin
from game.systems.settlements import SettlementsMixin
from game.systems.cache_events import CacheEventsMixin
from game.systems.restoration import RestorationMixin
from game.systems.state_migrations import StateMigrationsMixin
from game.systems.visited_recruitment import VisitedRecruitmentMixin
from game.systems.experience_scaling import ExperienceScalingMixin
from game.systems.quick_modules import QuickModulesMixin
from game.systems.equipment_upgrades import EquipmentUpgradesMixin
from game.systems.city_guides import CityGuidesMixin
from game.systems.retreat import RetreatMixin
from game.systems.leveled_contracts import LeveledContractsMixin
from game.systems.rarity_gates import RarityGatesMixin
from game.systems.combat import Combat
from game.systems.storms import Storms
from game.systems.shared_modules import SharedModulesMixin
from game.systems.equipment_maintenance import EquipmentMaintenanceMixin
from game.systems.enemy_completion import EnemyCompletionMixin
from game.systems.exploration_rewards import ExplorationRewardsMixin
from game.systems.metro_restoration import MetroRestorationMixin
from game.systems.story import StoryMixin
from game.systems.survival import Survival
from game.systems.authored_quests import AuthoredQuestsMixin
from game.systems.consumables import Consumables
from game.systems.credits import CreditsMixin
from game.systems.walking_reveal import WalkingRevealMixin
from game.systems.consumable_stock import ConsumableStockMixin
from game.systems.stash_access import StashAccessMixin
from game.systems.quest_experience import QuestExperienceMixin
from game.systems.recovery import Recovery
from game.systems.faction_combat import FactionCombatMixin
from game.systems.fence_passages import FencePassagesMixin
from game.systems.cache_feedback import CacheFeedbackMixin
from game.systems.battle_feedback import BattleFeedbackMixin
from game.systems.arena_exits import ArenaExitsMixin


class Game(
    FencePassagesMixin,
    CacheFeedbackMixin,
    BattleFeedbackMixin,
    ArenaExitsMixin,
    FactionCombatMixin,
    Recovery,
    CreditsMixin,
    WalkingRevealMixin,
    ConsumableStockMixin,
    StashAccessMixin,
    QuestExperienceMixin,
    Consumables,
    AuthoredQuestsMixin,
    Survival,
    StoryMixin,
    MetroRestorationMixin,
    SharedModulesMixin,
    EquipmentMaintenanceMixin,
    EnemyCompletionMixin,
    ExplorationRewardsMixin,
    Combat,
    Storms,
    RetreatMixin,
    LeveledContractsMixin,
    RarityGatesMixin,
    EquipmentUpgradesMixin,
    CityGuidesMixin,
    StateMigrationsMixin,
    VisitedRecruitmentMixin,
    ExperienceScalingMixin,
    QuickModulesMixin,
    RestorationMixin,
    CacheEventsMixin,
    SettlementsMixin,
    ScavengingMixin,
    ExpeditionsMixin,
    ContractsMixin,
    Guides,
    QuestSystem,
    Border,
    Reputation,
    FrontierMixin,
    EconomyMixin,
    AdventureMixin,
    ProgressionGame,
):
    """The complete game model, independent of launchers and presentation."""
