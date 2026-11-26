You need to do this with every model @[c:\Users\gabri\Documents\PROJETOS\POLI\Lab_Engenharia_Software\app\domain\models]. Also, everything on the codebase should be english, im slowly migrating, but consider everything you touch in domain should migrate. also no need to run tests.

Adjust plan and execute


Critical Issues in the Current Plan
1. @dataclass(slots=True) + Read-Only Property Aliases Will Crash
Under Approach #2, you plan to:

Refactor Track with @dataclass(slots=True) exposing English attributes (title, artist, etc.).

Add read-only property aliases for Portuguese names (titulo, artista, etc.).

Why it will fail: In CPython, when a class uses slots=True, @dataclass generates __slots__ based strictly on the annotated fields. If you declare properties on that slotted class that try to set or resolve attributes without explicit slots or if you accidentally annotate the aliases, Python raises ValueError: 'titulo' in __slots__ conflicts with class variable or AttributeError when instantiated.

The Root Architectural Smell: The guideline explicitly states:

"NEVER make the domain validation-library-shaped solely for transport."

Adding 10+ property aliases (titulo, artista, duracao_segundos, etc.) solely so that MusicaResponse.model_validate(track) doesn't break leaks transport-layer schema requirements directly into your domain model.

The Fix: Keep the domain entity pure. If you rename the domain entity's fields to English, map them explicitly in the repository or response mapper:

Python
# In api/mappers.py or schemas.py (Pydantic V2):
# Use Field(validation_alias="title") on MusicaResponse, 
# or construct it explicitly:
MusicaResponse(
    musica_id=track.id,
    titulo=track.title,
    artista=track.artist,
    ...
)

2. Constructor Field Ordering Trap (kw_only=True is Missing)
In Approach #2 and "Risks and Migration", you mention:

"Ordering dataclass fields to match the existing parameter order preserves positional argument instantiations"

In your current Musica.__init__, look closely at the parameter order:

Python
def __init__(
    self,
    musica_id: int | None,          # Has NO default
    titulo: str,                    # Has NO default
    artista: str,                   # Has NO default
    ...
    spotify_id: str | None = None,  # HAS default
    album: str | None = None,       # HAS default
    ...
)
If you order fields naturally, any field with a default cannot be followed by a field without a default. If someone passes positional arguments, relying on field declaration order in a 14-attribute class is notoriously brittle.

The Fix: Add kw_only=True to @dataclass(slots=True, kw_only=True). As established in your SWE rules:

"Prefer keyword-only instantiation (kw_only=True) to prevent silent parameter misalignments on wide entities."
Enforce explicit keyword instantiation (Musica(titulo="...", artista="...", ...)).

3. Database / Repository Hydration Bypass
In Approach #1, you remove @vote_points.setter so that points can only change via vote().

The Blind Spot: How does your database repository or ORM reconstitute a JamQueueItem from PostgreSQL / MySQL when reading an existing row that already has pontos_voto = 4?

If _pontos_voto has no setter and vote() only increments (self._pontos_voto += pontos), your repository won't be able to set the loaded points unless:

__init__ accepts pontos_voto: int = 0 (or vote_points: int = 0) to set the initial/persisted value upon hydration.

The field is initialized as a private attribute via dataclass:

Python
_pontos_voto: int = field(default=0)

@property
def pontos_voto(self) -> int:
    return self._pontos_voto
