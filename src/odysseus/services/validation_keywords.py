"""
Keyword lists for video validation.
"""

# Keywords that indicate a remastered/reissue version (studio albums, not live)
REMASTER_KEYWORDS = [
    'remaster',
    'remastered',
    'reissue',
    're-release',
    'deluxe edition',
    'anniversary edition'
]

# Live version detection keywords (word boundary patterns)
LIVE_WORD_BOUNDARY_KEYWORDS = [
    r'\blive\s+concert\b',  # "live concert"
    r'\blive\s+performance\b',  # "live performance"
    r'\blive\s+on\s+stage\b',  # "live on stage"
    r'\brecorded\s+live\b',  # "recorded live"
    r'\blive\s+session\b',  # "live session"
    r'\blive\s+recording\b',  # "live recording"
    r'\blive\s+from\b',  # "live from"
    r'\blive\s+@\b',  # "live @"
    r'\blive\s+in\b',  # "live in" (but not "live in" as part of song title)
    r'\blive\s+at\b',  # "live at" (e.g., "Live at Red Rocks")
    r'\blive\s+version\b',  # "live version"
    r'\blive\s+take\b',  # "live take"
    r'\blive\s+acoustic\b',  # "live acoustic"
    r'\blive\s+bootleg\b',  # "live bootleg"
    r'\blive\s+broadcast\b',  # "live broadcast"
]

# Live version detection keywords (simple substring match)
LIVE_SIMPLE_KEYWORDS = [
    'unplugged',
    'mtv unplugged',
    'kexp',
    'npr tiny desk',
    'audience',
    'applause',
    'encore'
]

# Known concert venues (strong indicators of live performances)
CONCERT_VENUES = [
    'red rocks',
    'madison square garden',
    'msg',
    'royal albert hall',
    'apollo theater',
    'apollo theatre',
    'fillmore',
    'hollywood bowl',
    'coachella',
    'glastonbury',
    'woodstock',
    'monterey pop',
    'newport folk',
    'newport jazz',
    'montreux jazz',
    'blue note',
    'village vanguard',
    'ronnie scott\'s',
    'ronnie scotts',
    'troubadour',
    'whisky a go go',
    'cbgb',
    'palladium',
    'hammersmith',
    'brixton academy',
    'o2 arena',
    'wembley',
    'festival',
    'festival de',
    'rock in rio',
    'lollapalooza',
    'bonnaroo',
    'sxsw',
    'austin city limits',
    'acoustic',
    'acoustic session'
]

# Explicit live indicators (patterns that always indicate live performance)
EXPLICIT_LIVE_PATTERNS = [
    r'\(live\)',  # "(Live)" or "(live)"
    r'\[live\]',  # "[Live]" or "[live]"
    r'- live',    # "- Live" or "- live"
    r': live',    # ": Live" or ": live"
    r'live!',     # "Live!" or "live!"
    r'live$',     # "Live" at end of title
]

# Reaction/review detection keywords (word boundary patterns)
REACTION_WORD_BOUNDARY_KEYWORDS = [
    r'\bvs\b',  # "vs" but not "versus" (handled separately)
    r'\brank\b',  # "rank" but not "ranking", "crank", etc.
    r'\brate\b',  # "rate" but not "create", "irate", etc.
]

# Top ranking patterns (for detecting ranking videos)
TOP_RANKING_PATTERNS = [
    r'\btop\s+\d+',  # "top 10", "top 5", etc.
    r'\btop\s+songs',  # "top songs"
    r'\btop\s+tracks',  # "top tracks"
    r'\btop\s+albums',  # "top albums"
    r'\btop\s+artists',  # "top artists"
    r'\btop\s+best',  # "top best"
    r'\btop\s+worst',  # "top worst"
]

# Reaction/review detection keywords (multi-word phrases)
REACTION_MULTI_WORD_PHRASES = [
    'first reaction',
    'first time listening',
    'first listen',
    'album review',
    'music review',
    'reaction to',
    'reacting to',
    'reacts to',
    'my reaction',
    'honest reaction',
    'genuine reaction',
    'blind reaction',
    'album reaction',
    'song reaction',
    'listening to',
    'listening session',
    'first time hearing',
    'lyrics explained',
    'album explained',
    'behind the scenes',
    'making of',
    'studio tour',
    'best moments',
    'tier list',
    'top 10',
    'top 5',
    'worst to best',
    'best to worst'
]

# Reaction/review detection keywords (specific single words)
REACTION_SPECIFIC_KEYWORDS = [
    'reaction',
    'react',
    'reacting',
    'reacts',
    'review',
    'unboxing',
    'unbox',
    'rating',
    'ranking',
    'worst',
    'best',
    'versus',
    'comparison',
    'breakdown',
    'analysis',
    'explained',
    'meaning',
    'discussion',
    'podcast',
    'interview',
    'documentary',
    'trailer',
    'teaser',
    'preview',
    'snippet',
    'clip',
    'excerpt',
    'highlights',
    'compilation',
    'mashup',
    'remix',
    'cover',
    'covers',
    'tribute',
    'parody',
    'meme',
    'funny',
    'comedy',
    'prank',
    'challenge',
]

