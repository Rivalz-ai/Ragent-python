from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union, Dict, Callable, Any
from uuid import UUID

#
# Basic Enums
#

class GoalStatus(str, Enum):
    DONE = "DONE"
    FAILED = "FAILED"
    IN_PROGRESS = "IN_PROGRESS"

class ModelClass(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EMBEDDING = "embedding"
    IMAGE = "image"

class ModelProviderName(str, Enum):
    OPENAI = "openai"
    ETERNALAI = "eternalai"
    ANTHROPIC = "anthropic"
    GROK = "grok"
    GROQ = "groq"
    LLAMACLOUD = "llama_cloud"
    TOGETHER = "together"
    LLAMALOCAL = "llama_local"
    GOOGLE = "google"
    CLAUDE_VERTEX = "claude_vertex"
    REDPILL = "redpill"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    HEURIST = "heurist"
    GALADRIEL = "galadriel"
    FAL = "falai"
    GAIANET = "gaianet"
    ALI_BAILIAN = "ali_bailian"
    VOLENGINE = "volengine"
    NANOGPT = "nanogpt"
    HYPERBOLIC = "hyperbolic"
    VENICE = "venice"
    AKASH_CHAT_API = "akash_chat_api"
    DEEPINFRA = "deepinfra"
    SUPERPROTOCOL = "super"

class Clients(str, Enum):
    DISCORD = "discord"
    DIRECT = "direct"
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    FARCASTER = "farcaster"
    LENS = "lens"
    AUTO = "auto"
    SLACK = "slack"

class ServiceType(str, Enum):
    IMAGE_DESCRIPTION = "image_description"
    TRANSCRIPTION = "transcription"
    VIDEO = "video"
    TEXT_GENERATION = "text_generation"
    BROWSER = "browser"
    SPEECH_GENERATION = "speech_generation"
    PDF = "pdf"
    INTIFACE = "intiface"
    AWS_S3 = "aws_s3"
    BUTTPLUG = "buttplug"
    SLACK = "slack"

class LoggingLevel(str, Enum):
    DEBUG = "debug"
    VERBOSE = "verbose"
    NONE = "none"

#
# Core Data Structures
#

@dataclass
class Media:
    id: str
    url: str
    title: str
    source: str
    description: str
    text: str
    contentType: Optional[str] = None

@dataclass
class Content:
    text: str
    action: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    inReplyTo: Optional[UUID] = None
    attachments: List[Media] = field(default_factory=list)
    # Additional dynamic properties
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ActionExample:
    user: str
    content: Content

@dataclass
class ConversationExample:
    userId: UUID
    content: Content

@dataclass
class ActorDetails:
    tagline: str
    summary: str
    quote: str

@dataclass
class Actor:
    name: str
    username: str
    details: ActorDetails
    id: UUID

@dataclass
class Objective:
    id: Optional[str]
    description: str
    completed: bool

@dataclass
class Goal:
    id: Optional[UUID]
    roomId: UUID
    userId: UUID
    name: str
    status: GoalStatus
    objectives: List[Objective]

@dataclass
class ModelSettings:
    maxInputTokens: int
    maxOutputTokens: int
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    stop: List[str] = field(default_factory=list)
    temperature: float = 1.0
    mode: Optional[str] = None

@dataclass
class ImageSettings:
    steps: Optional[int] = None

@dataclass
class ModelDefinition:
    endpoint: Optional[str]
    settings: ModelSettings
    imageSettings: Optional[ImageSettings]
    model: Dict[ModelClass, str]

@dataclass
class Memory:
    id: Optional[UUID]
    userId: UUID
    agentId: UUID
    createdAt: Optional[float]
    content: Content
    embedding: Optional[List[float]]
    roomId: UUID
    unique: Optional[bool] = False
    similarity: Optional[float] = None

@dataclass
class MessageExample:
    user: str
    content: Content

#
# Action & Evaluator
#

@dataclass
class EvaluationExample:
    context: str
    messages: List[ActionExample]
    outcome: str

# Handler and Validator placeholders
# runtime, message, state, options, callback -> Python function signature as needed

@dataclass
class Action:
    similes: List[str]
    description: str
    examples: List[List[ActionExample]]
    handler: Callable[..., Any]
    name: str
    validate: Callable[..., bool]

@dataclass
class Evaluator:
    alwaysRun: bool
    description: str
    similes: List[str]
    examples: List[EvaluationExample]
    handler: Callable[..., Any]
    name: str
    validate: Callable[..., bool]

@dataclass
class Provider:
    get: Callable[..., Any]

@dataclass
class Relationship:
    id: UUID
    userA: UUID
    userB: UUID
    userId: UUID
    roomId: UUID
    status: str
    createdAt: Optional[str] = None

@dataclass
class AccountDetails:
    summary: Optional[str] = None
    # Additional fields can be added here

@dataclass
class Account:
    id: UUID
    name: str
    username: str
    details: Optional[AccountDetails] = None
    email: Optional[str] = None
    avatarUrl: Optional[str] = None

@dataclass
class Participant:
    id: UUID
    account: Account

@dataclass
class Room:
    id: UUID
    participants: List[Participant]

@dataclass
class MessageState:
    userId: Optional[UUID]
    agentId: Optional[UUID]
    bio: str
    lore: str
    messageDirections: str
    postDirections: str
    roomId: UUID
    agentName: Optional[str]
    senderName: Optional[str]
    actors: str
    actorsData: Optional[List[Actor]]
    goals: Optional[str]
    goalsData: Optional[List[Goal]]
    recentMessages: str
    recentMessagesData: List[Memory]
    actionNames: Optional[str] = None
    actions: Optional[str] = None
    actionsData: Optional[List[Action]] = None
    actionExamples: Optional[str] = None
    providers: Optional[str] = None
    responseData: Optional[Content] = None
    recentInteractionsData: Optional[List[Memory]] = None
    recentInteractions: Optional[str] = None
    formattedConversation: Optional[str] = None
    knowledge: Optional[str] = None
    knowledgeData: Optional[List[Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

#
# Character / Plugin / Service
#

@dataclass
class Plugin:
    name: str
    description: str
    actions: Optional[List[Action]] = None
    providers: Optional[List[Provider]] = None
    evaluators: Optional[List[Evaluator]] = None
    services: Optional[List[Any]] = None
    clients: Optional[List[Any]] = None

@dataclass
class Character:
    id: Optional[UUID]
    name: str
    username: Optional[str]
    system: Optional[str]
    modelProvider: ModelProviderName
    imageModelProvider: Optional[ModelProviderName] = None
    modelEndpointOverride: Optional[str] = None
    templates: Optional[Dict[str, str]] = None
    bio: Union[str, List[str]] = field(default_factory=list)
    lore: List[str] = field(default_factory=list)
    messageExamples: List[List[MessageExample]] = field(default_factory=list)
    postExamples: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    adjectives: List[str] = field(default_factory=list)
    knowledge: Optional[List[str]] = None
    clients: List[Clients] = field(default_factory=list)
    plugins: List[Plugin] = field(default_factory=list)
    settings: Optional[Dict[str, Any]] = None
    clientConfig: Optional[Dict[str, Any]] = None
    style: Dict[str, List[str]] = field(default_factory=lambda: {
        "all": [],
        "chat": [],
        "post": []
    })
    twitterProfile: Optional[Dict[str, Any]] = None
    nft: Optional[Dict[str, str]] = None

#
# Database / Cache Adapters
#

@dataclass
class IDatabaseAdapter:
    """Placeholder for database operations"""
    db: Any

    async def init(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    # Example method:
    async def getAccountById(self, userId: UUID) -> Optional[Account]:
        raise NotImplementedError

    # Other methods omitted for brevity

@dataclass
class IDatabaseCacheAdapter:
    """Placeholder for cache operations"""

    async def getCache(self, agentId: UUID, key: str) -> Optional[str]:
        raise NotImplementedError

    async def setCache(self, agentId: UUID, key: str, value: str) -> bool:
        raise NotImplementedError

    async def deleteCache(self, agentId: UUID, key: str) -> bool:
        raise NotImplementedError

@dataclass
class IMemoryManager:
    runtime: Any
    tableName: str

    async def addEmbeddingToMemory(self, memory: Memory) -> Memory:
        raise NotImplementedError

    async def getMemories(self, roomId: UUID, count: int = 0,
                          unique: bool = False, start: Optional[int] = None,
                          end: Optional[int] = None) -> List[Memory]:
        raise NotImplementedError

    async def createMemory(self, memory: Memory, unique: bool = False) -> None:
        raise NotImplementedError

    # Other methods omitted for brevity

@dataclass
class CacheOptions:
    expires: Optional[int] = None

@dataclass
class ICacheManager:
    """Placeholder for caching interface"""

    async def get(self, key: str) -> Any:
        raise NotImplementedError

    async def set(self, key: str, value: Any, options: Optional[CacheOptions] = None) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

@dataclass
class KnowledgeItem:
    id: UUID
    content: Content

#
# Services
#

@dataclass
class Service:
    """Base Service abstraction"""

    @classmethod
    def getInstance(cls) -> Any:
        raise NotImplementedError

    async def initialize(self, runtime: Any) -> None:
        raise NotImplementedError

@dataclass
class ActionResponse:
    like: bool
    retweet: bool
    quote: Optional[bool] = None
    reply: Optional[bool] = None

#
# Common agent runtime interface placeholder
#

@dataclass
class IAgentRuntime:
    agentId: UUID
    serverUrl: str
    databaseAdapter: IDatabaseAdapter
    token: Optional[str]
    modelProvider: ModelProviderName
    imageModelProvider: ModelProviderName
    character: Character
    providers: List[Provider]
    actions: List[Action]
    evaluators: List[Evaluator]
    plugins: List[Plugin]
    fetch: Optional[Callable] = None
    messageManager: IMemoryManager = None
    descriptionManager: IMemoryManager = None
    documentsManager: IMemoryManager = None
    knowledgeManager: IMemoryManager = None
    loreManager: IMemoryManager = None
    cacheManager: ICacheManager = None
    services: Dict[ServiceType, Service] = field(default_factory=dict)
    clients: Dict[str, Any] = field(default_factory=dict)

    async def initialize(self) -> None:
        raise NotImplementedError

    def registerMemoryManager(self, manager: IMemoryManager) -> None:
        raise NotImplementedError

    def getMemoryManager(self, name: str) -> Optional[IMemoryManager]:
        raise NotImplementedError

    def getService(self, service: ServiceType) -> Optional[Service]:
        raise NotImplementedError

    def registerService(self, service: Service) -> None:
        raise NotImplementedError

    def getSetting(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def getConversationLength(self) -> int:
        raise NotImplementedError

    async def processActions(self, message: Memory, responses: List[Memory],
                             state: Any = None, callback: Optional[Callable] = None) -> None:
        raise NotImplementedError

    async def evaluate(self, message: Memory, state: Any = None, 
                       didRespond: bool = False, callback: Optional[Callable] = None) -> List[str]:
        raise NotImplementedError

    async def ensureParticipantExists(self, userId: UUID, roomId: UUID) -> None:
        raise NotImplementedError

    async def ensureUserExists(self, userId: UUID, userName: Optional[str],
                               name: Optional[str], source: Optional[str]) -> None:
        raise NotImplementedError

    def registerAction(self, action: Action) -> None:
        raise NotImplementedError

    async def ensureConnection(self, userId: UUID, roomId: UUID,
                               userName: Optional[str] = None,
                               userScreenName: Optional[str] = None,
                               source: Optional[str] = None) -> None:
        raise NotImplementedError

    async def ensureParticipantInRoom(self, userId: UUID, roomId: UUID) -> None:
        raise NotImplementedError

    async def ensureRoomExists(self, roomId: UUID) -> None:
        raise NotImplementedError

    async def composeState(self, message: Memory, additionalKeys: Dict[str, Any] = None) -> Any:
        raise NotImplementedError

    async def updateRecentMessageState(self, state: Any) -> Any:
        raise NotImplementedError