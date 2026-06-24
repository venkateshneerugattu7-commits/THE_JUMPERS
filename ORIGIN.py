#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║          BIP39 / BIP32 / BIP44 / BIP49 / BIP84  WALLET TOOLKIT         ║
║           WITH OPTIONAL COINCURVE ACCELERATION (if installed)          ║ THE JUMPERS ORIGIN)
╚══════════════════════════════════════════════════════════════════════════╝

Crypto primitives (pure Python, no pip needed):
  SHA-256 · RIPEMD-160 · HMAC-SHA-512 · PBKDF2-HMAC-SHA512
  secp256k1 point-mul (pure Python fallback) · Base58Check · Bech32

If coincurve is installed (pip install coincurve), secp256k1 operations are
up to 100x faster. The script auto-detects and uses it.
"""

# ══════════════════════════════════════════════════════════════════════════
# STDLIB IMPORTS ONLY
# ══════════════════════════════════════════════════════════════════════════
import hashlib, struct, sys, os, json, time, csv, re, unicodedata, mmap

# Optional file locking for parallel vault writes (Unix only; harmless on Windows)
HAS_FCNTL = False
HAS_MSVCRT = False
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        pass

def _lock_file(f, exclusive=True):
    """Cross-platform advisory file lock. Blocks indefinitely until acquired —
    matches fcntl.flock()'s blocking semantics on Unix.
    No-op if neither fcntl nor msvcrt are available."""
    if HAS_FCNTL:
        fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    elif HAS_MSVCRT:
        # msvcrt.locking only supports exclusive byte-range locks; lock a large
        # region starting at the current position to approximate whole-file lock.
        # NOTE: msvcrt's own LK_LOCK only retries internally for ~10s before
        # raising OSError — it does NOT block forever like fcntl does. We wrap it
        # in our own retry loop so a second instance waits indefinitely for the
        # lock to free up instead of giving up and writing the file unsafely.
        f.seek(0)
        while True:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1 << 30)
                break
            except OSError:
                time.sleep(0.25)   # lock still held elsewhere — keep waiting

def _unlock_file(f):
    if HAS_FCNTL:
        fcntl.flock(f, fcntl.LOCK_UN)
    elif HAS_MSVCRT:
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1 << 30)
        except OSError:
            pass

from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════
# OPTIONAL COINCURVE ACCELERATION
# ══════════════════════════════════════════════════════════════════════════
USE_COINCURVE = False
try:
    import coincurve
    USE_COINCURVE = True
except ImportError:
    pass

# ══════════════════════════════════════════════════════════════════════════
# ANSI TERMINAL COLOURS  (auto-disabled if not a tty)
# ══════════════════════════════════════════════════════════════════════════
_USE_COLOR = sys.stdout.isatty()

def _c(code): return f"\033[{code}m" if _USE_COLOR else ""

RESET  = _c("0")
BOLD   = _c("1")
DIM    = _c("2")
RED    = _c("31")
GREEN  = _c("32")
YELLOW = _c("33")
BLUE   = _c("34")
CYAN   = _c("36")
WHITE  = _c("37")
BRED   = _c("91")
BGRN   = _c("92")
BYEL   = _c("93")
BBLU   = _c("94")
BCYN   = _c("96")
BWHT   = _c("97")
BG_BLU = _c("44")
BG_GRN = _c("42")
BG_RED = _c("41")

W  = 76   # terminal width

# ── Navigation signal ─────────────────────────────────────────────────────
class _HomeSignal(Exception):
    """Raised anywhere to jump straight back to the main menu."""
    pass

def clr():
    os.system("cls" if os.name == "nt" else "clear")

def bar(char="═", w=W, col=CYAN):
    print(col + char * w + RESET)

def hdr(title, col=BCYN):
    bar("═", W, CYAN)
    total_pad = W - len(title) - 2
    left = total_pad // 2
    right = total_pad - left
    print(CYAN + "║" + " " * left + col + BOLD + title + RESET + CYAN +
          " " * right + "║" + RESET)
    bar("═", W, CYAN)

def section(title):
    print()
    print(CYAN + "┌─ " + BYEL + BOLD + title + RESET + CYAN +
          " " + "─" * max(0, W - len(title) - 4) + RESET)

def ok(msg):  print(BGRN + "  ✓  " + RESET + msg)
def err(msg): print(BRED + "  ✗  " + RESET + msg)
def info(msg):print(BBLU + "  ·  " + RESET + msg)
def warn(msg):print(BYEL + "  !  " + RESET + msg)

def prompt(msg, default=None):
    """Input with optional default.  Typing 'H' alone raises _HomeSignal → main menu."""
    suffix = f" [{default}]" if default is not None else ""
    try:
        v = input(BYEL + "  » " + RESET + msg + suffix + ": ").strip()
    except (EOFError, KeyboardInterrupt):
        print(); return default if default is not None else ""
    if v.upper() == "H":
        raise _HomeSignal
    return v if v else (default if default is not None else "")

def press_enter():
    """Waits for Enter.  Type 'H' to jump directly back to the Home menu."""
    try:
        v = input(DIM + "\n  [ Enter ] Continue   [ H ] Home menu  " + RESET).strip().lower()
        if v == 'h':
            raise _HomeSignal
    except _HomeSignal:
        raise                          # propagate upward
    except (EOFError, KeyboardInterrupt):
        pass

def yn(msg, default="n"):
    """Yes/no prompt.  Typing 'H' alone raises _HomeSignal → main menu."""
    r = prompt(msg + " (y/n)", default).lower()
    if r == "h":          # prompt() raises before reaching here, but guard anyway
        raise _HomeSignal
    return r.startswith("y")

def spin(msg, done=False):
    """Single-line progress indicator."""
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    if done:
        sys.stdout.write("\r" + " " * (W) + "\r")
        sys.stdout.flush()
    else:
        f = frames[int(time.time()*10) % len(frames)]
        sys.stdout.write(f"\r  {CYAN}{f}{RESET}  {msg[:W-6]}")
        sys.stdout.flush()


# ══════════════════════════════════════════════════════════════════════════
# HUNT UTILITIES  — ETA, rolling speed, pause flag, hunt log
# ══════════════════════════════════════════════════════════════════════════
_PAUSE_FLAG  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunt_pause.flag")
_HUNT_LOG    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunt_log.txt")
_SPEED_WINDOW = 10      # seconds for rolling-average speed window

class _EtaTracker:
    """Rolling-window speed + ETA calculator for hunt loops."""
    def __init__(self):
        self._samples = []          # list of (timestamp, cumulative_count)
        self._t0      = time.time()

    def tick(self, done_count, total):
        """Call once per iteration.  Returns (rate_str, eta_str)."""
        now = time.time()
        self._samples.append((now, done_count))
        # Keep only samples inside the rolling window
        cutoff = now - _SPEED_WINDOW
        self._samples = [(t, c) for t, c in self._samples if t >= cutoff]

        if len(self._samples) >= 2:
            dt  = self._samples[-1][0] - self._samples[0][0]
            dc  = self._samples[-1][1] - self._samples[0][1]
            rate = dc / dt if dt > 0 else 0
        else:
            elapsed = now - self._t0
            rate    = done_count / elapsed if elapsed > 0 else 0

        if rate > 0 and total and total > done_count:
            secs_left = (total - done_count) / rate
            if secs_left < 3600:
                eta_str = f"{int(secs_left//60):02d}:{int(secs_left%60):02d}"
            elif secs_left < 86400:
                h = int(secs_left//3600); m = int((secs_left%3600)//60)
                eta_str = f"{h}h{m:02d}m"
            else:
                days = int(secs_left // 86400)
                h    = int((secs_left % 86400) // 3600)
                eta_str = f"{days}d{h:02d}h"
        else:
            eta_str = "--:--"

        if   rate >= 1_000_000: rate_str = f"{rate/1_000_000:.1f}M/s"
        elif rate >= 1_000:     rate_str = f"{rate/1_000:.1f}K/s"
        else:                   rate_str = f"{int(rate)}/s"

        return rate_str, eta_str

def check_pause_flag():
    """Block execution while hunt_pause.flag exists (background-friendly pause)."""
    if os.path.isfile(_PAUSE_FLAG):
        spin("", done=True)
        print(f"  {BYEL}⏸  Paused — delete hunt_pause.flag to resume …{RESET}", flush=True)
        while os.path.isfile(_PAUSE_FLAG):
            time.sleep(0.5)
        print(f"  {BGRN}▶  Resumed{RESET}", flush=True)

def hunt_log_match(mode_tag, mnemonic, addrs, rank=None):
    """Append a match line to hunt_log.txt."""
    try:
        with open(_HUNT_LOG, "a", encoding="utf-8") as fh:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            rank_str = f"  rank={rank}" if rank is not None else ""
            fh.write(f"[{ts}] MATCH  mode={mode_tag}{rank_str}\n")
            fh.write(f"  mnemonic: {mnemonic}\n")
            for a in addrs:
                fh.write(f"  {a['type']:8s} {a['address']}  path={a['path']}\n")
            fh.write("\n")
    except Exception:
        pass

def hunt_log_session(mode_tag, scanned, valid_count, found_count, elapsed):
    """Append a session summary line to hunt_log.txt."""
    try:
        with open(_HUNT_LOG, "a", encoding="utf-8") as fh:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            fh.write(
                f"[{ts}] SESSION  mode={mode_tag}  "
                f"scanned={scanned:,}  valid={valid_count:,}  "
                f"found={found_count}  elapsed={elapsed:.1f}s\n\n"
            )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════
# BIP39 WORDLIST — 2048 words (official)
# ══════════════════════════════════════════════════════════════════════════
WORDLIST = [
    "abandon","ability","able","about","above","absent","absorb","abstract",
    "absurd","abuse","access","accident","account","accuse","achieve","acid",
    "acoustic","acquire","across","act","action","actor","actress","actual",
    "adapt","add","addict","address","adjust","admit","adult","advance",
    "advice","aerobic","affair","afford","afraid","again","age","agent",
    "agree","ahead","aim","air","airport","aisle","alarm","album",
    "alcohol","alert","alien","all","alley","allow","almost","alone",
    "alpha","already","also","alter","always","amateur","amazing","among",
    "amount","amused","analyst","anchor","ancient","anger","angle","angry",
    "animal","ankle","announce","annual","another","answer","antenna","antique",
    "anxiety","any","apart","apology","appear","apple","approve","april",
    "arch","arctic","area","arena","argue","arm","armed","armor",
    "army","around","arrange","arrest","arrive","arrow","art","artefact",
    "artist","artwork","ask","aspect","assault","asset","assist","assume",
    "asthma","athlete","atom","attack","attend","attitude","attract","auction",
    "audit","august","aunt","author","auto","autumn","average","avocado",
    "avoid","awake","aware","away","awesome","awful","awkward","axis",
    "baby","bachelor","bacon","badge","bag","balance","balcony","ball",
    "bamboo","banana","banner","bar","barely","bargain","barrel","base",
    "basic","basket","battle","beach","bean","beauty","because","become",
    "beef","before","begin","behave","behind","believe","below","belt",
    "bench","benefit","best","betray","better","between","beyond","bicycle",
    "bid","bike","bind","biology","bird","birth","bitter","black",
    "blade","blame","blanket","blast","bleak","bless","blind","blood",
    "blossom","blouse","blue","blur","blush","board","boat","body",
    "boil","bomb","bone","bonus","book","boost","border","boring",
    "borrow","boss","bottom","bounce","box","boy","bracket","brain",
    "brand","brass","brave","bread","breeze","brick","bridge","brief",
    "bright","bring","brisk","broccoli","broken","bronze","broom","brother",
    "brown","brush","bubble","buddy","budget","buffalo","build","bulb",
    "bulk","bullet","bundle","bunker","burden","burger","burst","bus",
    "business","busy","butter","buyer","buzz","cabbage","cabin","cable",
    "cactus","cage","cake","call","calm","camera","camp","can",
    "canal","cancel","candy","cannon","canoe","canvas","canyon","capable",
    "capital","captain","car","carbon","card","cargo","carpet","carry",
    "cart","case","cash","casino","castle","casual","cat","catalog",
    "catch","category","cattle","caught","cause","caution","cave","ceiling",
    "celery","cement","census","century","cereal","certain","chair","chalk",
    "champion","change","chaos","chapter","charge","chase","chat","cheap",
    "check","cheese","chef","cherry","chest","chicken","chief","child",
    "chimney","choice","choose","chronic","chuckle","chunk","churn","cigar",
    "cinnamon","circle","citizen","city","civil","claim","clap","clarify",
    "claw","clay","clean","clerk","clever","click","client","cliff",
    "climb","clinic","clip","clock","clog","close","cloth","cloud",
    "clown","club","clump","cluster","clutch","coach","coast","coconut",
    "code","coffee","coil","coin","collect","color","column","combine",
    "come","comfort","comic","common","company","concert","conduct","confirm",
    "congress","connect","consider","control","convince","cook","cool","copper",
    "copy","coral","core","corn","correct","cost","cotton","couch",
    "country","couple","course","cousin","cover","coyote","crack","cradle",
    "craft","cram","crane","crash","crater","crawl","crazy","cream",
    "credit","creek","crew","cricket","crime","crisp","critic","crop",
    "cross","crouch","crowd","crucial","cruel","cruise","crumble","crunch",
    "crush","cry","crystal","cube","culture","cup","cupboard","curious",
    "current","curtain","curve","cushion","custom","cute","cycle","dad",
    "damage","damp","dance","danger","daring","dash","daughter","dawn",
    "day","deal","debate","debris","decade","december","decide","decline",
    "decorate","decrease","deer","defense","define","defy","degree","delay",
    "deliver","demand","demise","denial","dentist","deny","depart","depend",
    "deposit","depth","deputy","derive","describe","desert","design","desk",
    "despair","destroy","detail","detect","develop","device","devote","diagram",
    "dial","diamond","diary","dice","diesel","diet","differ","digital",
    "dignity","dilemma","dinner","dinosaur","direct","dirt","disagree","discover",
    "disease","dish","dismiss","disorder","display","distance","divert","divide",
    "divorce","dizzy","doctor","document","dog","doll","dolphin","domain",
    "donate","donkey","donor","door","dose","double","dove","draft",
    "dragon","drama","drastic","draw","dream","dress","drift","drill",
    "drink","drip","drive","drop","drum","dry","duck","dumb",
    "dune","during","dust","dutch","duty","dwarf","dynamic","eager",
    "eagle","early","earn","earth","easily","east","easy","echo",
    "ecology","economy","edge","edit","educate","effort","egg","eight",
    "either","elbow","elder","electric","elegant","element","elephant","elevator",
    "elite","else","embark","embody","embrace","emerge","emotion","employ",
    "empower","empty","enable","enact","end","endless","endorse","enemy",
    "energy","enforce","engage","engine","enhance","enjoy","enlist","enough",
    "enrich","enroll","ensure","enter","entire","entry","envelope","episode",
    "equal","equip","era","erase","erode","erosion","error","erupt",
    "escape","essay","essence","estate","eternal","ethics","evidence","evil",
    "evoke","evolve","exact","example","excess","exchange","excite","exclude",
    "excuse","execute","exercise","exhaust","exhibit","exile","exist","exit",
    "exotic","expand","expect","expire","explain","expose","express","extend",
    "extra","eye","eyebrow","fabric","face","faculty","fade","faint",
    "faith","fall","false","fame","family","famous","fan","fancy",
    "fantasy","farm","fashion","fat","fatal","father","fatigue","fault",
    "favorite","feature","february","federal","fee","feed","feel","female",
    "fence","festival","fetch","fever","few","fiber","fiction","field",
    "figure","file","film","filter","final","find","fine","finger",
    "finish","fire","firm","first","fiscal","fish","fit","fitness",
    "fix","flag","flame","flash","flat","flavor","flee","flight",
    "flip","float","flock","floor","flower","fluid","flush","fly",
    "foam","focus","fog","foil","fold","follow","food","foot",
    "force","forest","forget","fork","fortune","forum","forward","fossil",
    "foster","found","fox","fragile","frame","frequent","fresh","friend",
    "fringe","frog","front","frost","frown","frozen","fruit","fuel",
    "fun","funny","furnace","fury","future","gadget","gain","galaxy",
    "gallery","game","gap","garage","garbage","garden","garlic","garment",
    "gas","gasp","gate","gather","gauge","gaze","general","genius",
    "genre","gentle","genuine","gesture","ghost","giant","gift","giggle",
    "ginger","giraffe","girl","give","glad","glance","glare","glass",
    "glide","glimpse","globe","gloom","glory","glove","glow","glue",
    "goat","goddess","gold","good","goose","gorilla","gospel","gossip",
    "govern","gown","grab","grace","grain","grant","grape","grass",
    "gravity","great","green","grid","grief","grit","grocery","group",
    "grow","grunt","guard","guess","guide","guilt","guitar","gun",
    "gym","habit","hair","half","hammer","hamster","hand","happy",
    "harbor","hard","harsh","harvest","hat","have","hawk","hazard",
    "head","health","heart","heavy","hedgehog","height","hello","helmet",
    "help","hen","hero","hidden","high","hill","hint","hip",
    "hire","history","hobby","hockey","hold","hole","holiday","hollow",
    "home","honey","hood","hope","horn","horror","horse","hospital",
    "host","hotel","hour","hover","hub","huge","human","humble",
    "humor","hundred","hungry","hunt","hurdle","hurry","hurt","husband",
    "hybrid","ice","icon","idea","identify","idle","ignore","ill",
    "illegal","illness","image","imitate","immense","immune","impact","impose",
    "improve","impulse","inch","include","income","increase","index","indicate",
    "indoor","industry","infant","inflict","inform","inhale","inherit","initial",
    "inject","injury","inmate","inner","innocent","input","inquiry","insane",
    "insect","inside","inspire","install","intact","interest","into","invest",
    "invite","involve","iron","island","isolate","issue","item","ivory",
    "jacket","jaguar","jar","jazz","jealous","jeans","jelly","jewel",
    "job","join","joke","journey","joy","judge","juice","jump",
    "jungle","junior","junk","just","kangaroo","keen","keep","ketchup",
    "key","kick","kid","kidney","kind","kingdom","kiss","kit",
    "kitchen","kite","kitten","kiwi","knee","knife","knock","know",
    "lab","label","labor","ladder","lady","lake","lamp","language",
    "laptop","large","later","latin","laugh","laundry","lava","law",
    "lawn","lawsuit","layer","lazy","leader","leaf","learn","leave",
    "lecture","left","leg","legal","legend","leisure","lemon","lend",
    "length","lens","leopard","lesson","letter","level","liar","liberty",
    "library","license","life","lift","light","like","limb","limit",
    "link","lion","liquid","list","little","live","lizard","load",
    "loan","lobster","local","lock","logic","lonely","long","loop",
    "lottery","loud","lounge","love","loyal","lucky","luggage","lumber",
    "lunar","lunch","luxury","lyrics","machine","mad","magic","magnet",
    "maid","mail","main","major","make","mammal","man","manage",
    "mandate","mango","mansion","manual","maple","marble","march","margin",
    "marine","market","marriage","mask","mass","master","match","material",
    "math","matrix","matter","maximum","maze","meadow","mean","measure",
    "meat","mechanic","medal","media","melody","melt","member","memory",
    "mention","menu","mercy","merge","merit","merry","mesh","message",
    "metal","method","middle","midnight","milk","million","mimic","mind",
    "minimum","minor","minute","miracle","mirror","misery","miss","mistake",
    "mix","mixed","mixture","mobile","model","modify","mom","moment",
    "monitor","monkey","monster","month","moon","moral","more","morning",
    "mosquito","mother","motion","motor","mountain","mouse","move","movie",
    "much","muffin","mule","multiply","muscle","museum","mushroom","music",
    "must","mutual","myself","mystery","myth","naive","name","napkin",
    "narrow","nasty","nation","nature","near","neck","need","negative",
    "neglect","neither","nephew","nerve","nest","net","network","neutral",
    "never","news","next","nice","night","noble","noise","nominee",
    "noodle","normal","north","nose","notable","note","nothing","notice",
    "novel","now","nuclear","number","nurse","nut","oak","obey",
    "object","oblige","obscure","observe","obtain","obvious","occur","ocean",
    "october","odor","off","offer","office","often","oil","okay",
    "old","olive","olympic","omit","once","one","onion","online",
    "only","open","opera","opinion","oppose","option","orange","orbit",
    "orchard","order","ordinary","organ","orient","original","orphan","ostrich",
    "other","outdoor","outer","output","outside","oval","oven","over",
    "own","owner","oxygen","oyster","ozone","pact","paddle","page",
    "pair","palace","palm","panda","panel","panic","panther","paper",
    "parade","parent","park","parrot","party","pass","patch","path",
    "patient","patrol","pattern","pause","pave","payment","peace","peanut",
    "pear","peasant","pelican","pen","penalty","pencil","people","pepper",
    "perfect","permit","person","pet","phone","photo","phrase","physical",
    "piano","picnic","picture","piece","pig","pigeon","pill","pilot",
    "pink","pioneer","pipe","pistol","pitch","pizza","place","planet",
    "plastic","plate","play","please","pledge","pluck","plug","plunge",
    "poem","poet","point","polar","pole","police","pond","pony",
    "pool","popular","portion","position","possible","post","potato","pottery",
    "poverty","powder","power","practice","praise","predict","prefer","prepare",
    "present","pretty","prevent","price","pride","primary","print","priority",
    "prison","private","prize","problem","process","produce","profit","program",
    "project","promote","proof","property","prosper","protect","proud","provide",
    "public","pudding","pull","pulp","pulse","pumpkin","punch","pupil",
    "puppy","purchase","purity","purpose","purse","push","put","puzzle",
    "pyramid","quality","quantum","quarter","question","quick","quit","quiz",
    "quote","rabbit","raccoon","race","rack","radar","radio","rail",
    "rain","raise","rally","ramp","ranch","random","range","rapid",
    "rare","rate","rather","raven","raw","razor","ready","real",
    "reason","rebel","rebuild","recall","receive","recipe","record","recycle",
    "reduce","reflect","reform","refuse","region","regret","regular","reject",
    "relax","release","relief","rely","remain","remember","remind","remove",
    "render","renew","rent","reopen","repair","repeat","replace","report",
    "require","rescue","resemble","resist","resource","response","result","retire",
    "retreat","return","reunion","reveal","review","reward","rhythm","rib",
    "ribbon","rice","rich","ride","ridge","rifle","right","rigid",
    "ring","riot","ripple","risk","ritual","rival","river","road",
    "roast","robot","robust","rocket","romance","roof","rookie","room",
    "rose","rotate","rough","round","route","royal","rubber","rude",
    "rug","rule","run","runway","rural","sad","saddle","sadness",
    "safe","sail","salad","salmon","salon","salt","salute","same",
    "sample","sand","satisfy","satoshi","sauce","sausage","save","say",
    "scale","scan","scare","scatter","scene","scheme","school","science",
    "scissors","scorpion","scout","scrap","screen","script","scrub","sea",
    "search","season","seat","second","secret","section","security","seed",
    "seek","segment","select","sell","seminar","senior","sense","sentence",
    "series","service","session","settle","setup","seven","shadow","shaft",
    "shallow","share","shed","shell","sheriff","shield","shift","shine",
    "ship","shiver","shock","shoe","shoot","shop","short","shoulder",
    "shove","shrimp","shrug","shuffle","shy","sibling","sick","side",
    "siege","sight","sign","silent","silk","silly","silver","similar",
    "simple","since","sing","siren","sister","situate","six","size",
    "skate","sketch","ski","skill","skin","skirt","skull","slab",
    "slam","sleep","slender","slice","slide","slight","slim","slogan",
    "slot","slow","slush","small","smart","smile","smoke","smooth",
    "snack","snake","snap","sniff","snow","soap","soccer","social",
    "sock","soda","soft","solar","soldier","solid","solution","solve",
    "someone","song","soon","sorry","sort","soul","sound","soup",
    "source","south","space","spare","spatial","spawn","speak","special",
    "speed","spell","spend","sphere","spice","spider","spike","spin",
    "spirit","split","spoil","sponsor","spoon","sport","spot","spray",
    "spread","spring","spy","square","squeeze","squirrel","stable","stadium",
    "staff","stage","stairs","stamp","stand","start","state","stay",
    "steak","steel","stem","step","stereo","stick","still","sting",
    "stock","stomach","stone","stool","story","stove","strategy","street",
    "strike","strong","struggle","student","stuff","stumble","style","subject",
    "submit","subway","success","such","sudden","suffer","sugar","suggest",
    "suit","summer","sun","sunny","sunset","super","supply","supreme",
    "sure","surface","surge","surprise","surround","survey","suspect","sustain",
    "swallow","swamp","swap","swarm","swear","sweet","swift","swim",
    "swing","switch","sword","symbol","symptom","syrup","system","table",
    "tackle","tag","tail","talent","talk","tank","tape","target",
    "task","taste","tattoo","taxi","teach","team","tell","ten",
    "tenant","tennis","tent","term","test","text","thank","that",
    "theme","then","theory","there","they","thing","this","thought",
    "three","thrive","throw","thumb","thunder","ticket","tide","tiger",
    "tilt","timber","time","tiny","tip","tired","tissue","title",
    "toast","tobacco","today","toddler","toe","together","toilet","token",
    "tomato","tomorrow","tone","tongue","tonight","tool","tooth","top",
    "topic","topple","torch","tornado","tortoise","toss","total","tourist",
    "toward","tower","town","toy","track","trade","traffic","tragic",
    "train","transfer","trap","trash","travel","tray","treat","tree",
    "trend","trial","tribe","trick","trigger","trim","trip","trophy",
    "trouble","truck","true","truly","trumpet","trust","truth","try",
    "tube","tuition","tumble","tuna","tunnel","turkey","turn","turtle",
    "twelve","twenty","twice","twin","twist","two","type","typical",
    "ugly","umbrella","unable","unaware","uncle","uncover","under","undo",
    "unfair","unfold","unhappy","uniform","unique","unit","universe","unknown",
    "unlock","until","unusual","unveil","update","upgrade","uphold","upon",
    "upper","upset","urban","urge","usage","use","used","useful",
    "useless","usual","utility","vacant","vacuum","vague","valid","valley",
    "valve","van","vanish","vapor","various","vast","vault","vehicle",
    "velvet","vendor","venture","venue","verb","verify","version","very",
    "vessel","veteran","viable","vibrant","vicious","victory","video","view",
    "village","vintage","violin","virtual","virus","visa","visit","visual",
    "vital","vivid","vocal","voice","void","volcano","volume","vote",
    "voyage","wage","wagon","wait","walk","wall","walnut","want",
    "warfare","warm","warrior","wash","wasp","waste","water","wave",
    "way","wealth","weapon","wear","weasel","weather","web","wedding",
    "weekend","weird","welcome","west","wet","whale","what","wheat",
    "wheel","when","where","whip","whisper","wide","width","wife",
    "wild","will","win","window","wine","wing","wink","winner",
    "winter","wire","wisdom","wise","wish","witness","wolf","woman",
    "wonder","wood","wool","word","work","world","worry","worth",
    "wrap","wreck","wrestle","wrist","write","wrong","yard","year",
    "yellow","you","young","youth","zebra","zero","zone","zoo",
]
assert len(WORDLIST) == 2048

# ══════════════════════════════════════════════════════════════════════════
# SHA-256  (pure Python, FIPS 180-4)
# ══════════════════════════════════════════════════════════════════════════
_SHA256_K = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
]
def _sha256_block(block, state):
    def rotr(x,n): return ((x>>n)|(x<<(32-n)))&0xFFFFFFFF
    w = list(struct.unpack('>16I', block))
    for i in range(16,64):
        s0=rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3)
        s1=rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10)
        w.append((w[i-16]+s0+w[i-7]+s1)&0xFFFFFFFF)
    a,b,c,d,e,f,g,h=state
    for i in range(64):
        S1=(rotr(e,6)^rotr(e,11)^rotr(e,25))
        ch=(e&f)^(~e&g)
        t1=(h+S1+ch+_SHA256_K[i]+w[i])&0xFFFFFFFF
        S0=(rotr(a,2)^rotr(a,13)^rotr(a,22))
        maj=(a&b)^(a&c)^(b&c)
        t2=(S0+maj)&0xFFFFFFFF
        h,g,f,e,d,c,b,a=g,f,e,(d+t1)&0xFFFFFFFF,c,b,a,(t1+t2)&0xFFFFFFFF
    return [(s+v)&0xFFFFFFFF for s,v in zip(state,[a,b,c,d,e,f,g,h])]

def _sha256_pure(data):
    """Pure-Python SHA-256 fallback (kept for environments without hashlib access)."""
    state=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
           0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
    msg=bytearray(data); orig=len(data)
    msg.append(0x80)
    while len(msg)%64!=56: msg.append(0)
    msg+=struct.pack('>Q',orig*8)
    for i in range(0,len(msg),64): state=_sha256_block(bytes(msg[i:i+64]),state)
    return struct.pack('>8I',*state)

def sha256(data):
    """SHA-256 via hashlib (OpenSSL-backed, C-accelerated). Massively faster than
    the pure-Python block-transform loop — hashlib.sha256 is always available in
    every CPython build, so there is no fallback risk here."""
    return hashlib.sha256(data).digest()

def hash256(data): return sha256(sha256(data))

# ══════════════════════════════════════════════════════════════════════════
# RIPEMD-160  (pure Python, ISO/IEC 10118-3)
# ══════════════════════════════════════════════════════════════════════════
_RL=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
_RR=[5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
_SL=[11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
_SR=[8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
_KL=[0,0x5A827999,0x6ED9EBA1,0x8F1BBCDC,0xA953FD4E]
_KR=[0x50A28BE6,0x5C4DD124,0x6D703EF3,0x7A6D76E9,0]

def _ripemd160_pure(data):
    """Pure-Python RIPEMD-160 fallback — used only if hashlib's OpenSSL backend
    doesn't expose ripemd160 (some OpenSSL 3.x builds disable legacy digests)."""
    def rol(x,n): return ((x<<n)|(x>>(32-n)))&0xFFFFFFFF
    def f(j,x,y,z):
        if j<16: return x^y^z
        elif j<32: return (x&y)|(~x&z)
        elif j<48: return (x|~y)^z
        elif j<64: return (x&z)|(y&~z)
        else: return x^(y|~z)
    msg=bytearray(data); orig=len(data)
    msg.append(0x80)
    while len(msg)%64!=56: msg.append(0)
    msg+=struct.pack('<Q',orig*8)
    h=[0x67452301,0xEFCDAB89,0x98BADCFE,0x10325476,0xC3D2E1F0]
    for blk in range(0,len(msg),64):
        X=struct.unpack('<16I',msg[blk:blk+64])
        al,bl,cl,dl,el=h; ar,br,cr,dr,er=h
        for j in range(80):
            T=rol((al+f(j,bl,cl,dl)+X[_RL[j]]+_KL[j//16])&0xFFFFFFFF,_SL[j])
            T=(T+el)&0xFFFFFFFF; al,bl,cl,dl,el=el,T,bl,rol(cl,10),dl
        for j in range(80):
            T=rol((ar+f(79-j,br,cr,dr)+X[_RR[j]]+_KR[j//16])&0xFFFFFFFF,_SR[j])
            T=(T+er)&0xFFFFFFFF; ar,br,cr,dr,er=er,T,br,rol(cr,10),dr
        T=(h[1]+cl+dr)&0xFFFFFFFF
        h[1]=(h[2]+dl+er)&0xFFFFFFFF; h[2]=(h[3]+el+ar)&0xFFFFFFFF
        h[3]=(h[4]+al+br)&0xFFFFFFFF; h[4]=(h[0]+bl+cr)&0xFFFFFFFF; h[0]=T
    return struct.pack('<5I',*h)

# Detect once at import time whether this Python's OpenSSL build exposes ripemd160.
# Verified against the official empty-string test vector, not just "didn't throw" —
# some OpenSSL providers register the name but return wrong digests, so we check output.
try:
    _RMD_PROBE = hashlib.new('ripemd160', b'').digest()
    _HAS_HASHLIB_RMD160 = (_RMD_PROBE == bytes.fromhex('9c1185a5c5e9fc54612808977ee8f548b2258d31'))
except Exception:
    _HAS_HASHLIB_RMD160 = False

def ripemd160(data):
    """RIPEMD-160 via hashlib when the OpenSSL backend supports it (C-accelerated,
    much faster); transparently falls back to the verified pure-Python implementation
    otherwise. Either path is checked against the official test vector at startup
    by run_tests(), so correctness is guaranteed regardless of which path is active."""
    if _HAS_HASHLIB_RMD160:
        return hashlib.new('ripemd160', data).digest()
    return _ripemd160_pure(data)

def hash160(data): return ripemd160(sha256(data))

# ══════════════════════════════════════════════════════════════════════════
# HMAC-SHA-512  (stdlib wrapping — zero pure-Python overhead)
# ══════════════════════════════════════════════════════════════════════════
def hmac_sha512(key, data):
    blk=128
    if len(key)>blk: key=hashlib.sha512(key).digest()
    key=key.ljust(blk,b'\x00')
    ipad=bytes(b^0x36 for b in key); opad=bytes(b^0x5C for b in key)
    return hashlib.sha512(opad+hashlib.sha512(ipad+data).digest()).digest()

# ══════════════════════════════════════════════════════════════════════════
# PBKDF2-HMAC-SHA512  (stdlib C path → fast)
# ══════════════════════════════════════════════════════════════════════════
def pbkdf2_hmac_sha512(password, salt, iterations, dklen=64):
    try:
        return hashlib.pbkdf2_hmac('sha512', password, salt, iterations, dklen)
    except Exception:
        import math
        dk = b""
        for i in range(1, math.ceil(dklen / 64) + 1):
            U = hmac_sha512(password, salt + struct.pack('>I', i))
            T = bytearray(U)
            for _ in range(iterations - 1):
                U = hmac_sha512(password, U)
                T = bytearray(x ^ y for x, y in zip(T, U))
            dk += bytes(T)
        return dk[:dklen]

# ══════════════════════════════════════════════════════════════════════════
# secp256k1 — PURE PYTHON FALLBACK (used only if coincurve is missing)
# ══════════════════════════════════════════════════════════════════════════
_P  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

def _inv(a): return pow(a,_P-2,_P)

def _pt_add(P1,P2):
    if P1 is None: return P2
    if P2 is None: return P1
    x1,y1=P1; x2,y2=P2
    if x1==x2:
        if y1!=y2: return None
        lam=(3*x1*x1*_inv(2*y1))%_P
    else:
        lam=((y2-y1)*_inv(x2-x1))%_P
    x3=(lam*lam-x1-x2)%_P; y3=(lam*(x1-x3)-y1)%_P
    return (x3,y3)

def _pt_mul(k,P):
    R=None; Q=P
    while k:
        if k&1: R=_pt_add(R,Q)
        Q=_pt_add(Q,Q); k>>=1
    return R

def privkey_to_pubkey(priv: bytes) -> bytes:
    if USE_COINCURVE:
        return coincurve.PrivateKey(priv).public_key.format(compressed=True)
    k = int.from_bytes(priv, 'big')
    x, y = _pt_mul(k, (_Gx, _Gy))
    return (b'\x02' if y % 2 == 0 else b'\x03') + x.to_bytes(32, 'big')

# ══════════════════════════════════════════════════════════════════════════
# BASE58CHECK
# ══════════════════════════════════════════════════════════════════════════
_B58='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def base58check_encode(payload):
    cs=hash256(payload)[:4]; data=payload+cs
    lz=len(data)-len(data.lstrip(b'\x00'))
    num=int.from_bytes(data,'big'); chars=[]
    while num: num,r=divmod(num,58); chars.append(_B58[r])
    return '1'*lz+''.join(reversed(chars))

# ══════════════════════════════════════════════════════════════════════════
# BECH32 (BIP173)
# ══════════════════════════════════════════════════════════════════════════
_BECH32='qpzry9x8gf2tvdw0s3jn54khce6mua7l'

def _b32poly(v):
    G=[0x3b6a57b2,0x26508e6d,0x1ea119fa,0x3d4233dd,0x2a1462b3]; c=1
    for x in v:
        b=c>>25; c=((c&0x1FFFFFF)<<5)^x
        for i in range(5): c^=G[i] if (b>>i)&1 else 0
    return c

def _b32hrp(hrp):
    return [ord(c)>>5 for c in hrp]+[0]+[ord(c)&31 for c in hrp]

def _cvtbits(data,fr,to):
    acc=bits=0; ret=[]; mx=(1<<to)-1; ma=(1<<(fr+to-1))-1
    for v in data:
        acc=((acc<<fr)|v)&ma; bits+=fr
        while bits>=to: bits-=to; ret.append((acc>>bits)&mx)
    if bits: ret.append((acc<<(to-bits))&mx)
    return ret

def bech32_encode(hrp, witprog):
    data=[0]+_cvtbits(witprog,8,5)
    poly=_b32poly(_b32hrp(hrp)+data+[0]*6)^1
    cs=[(poly>>(5*(5-i)))&31 for i in range(6)]
    return hrp+'1'+''.join(_BECH32[d] for d in data+cs)

# ══════════════════════════════════════════════════════════════════════════
# BIP32 child key derivation
# ══════════════════════════════════════════════════════════════════════════
def ckd_priv(parent_key, parent_chain, index, hardened):
    if hardened:
        data=b'\x00'+parent_key+index.to_bytes(4,'big')
    else:
        data=privkey_to_pubkey(parent_key)+index.to_bytes(4,'big')
    I=hmac_sha512(parent_chain,data); IL,IR=I[:32],I[32:]
    il=int.from_bytes(IL,'big')
    if il>=_N: raise ValueError("BIP32: IL>=n")
    child=(il+int.from_bytes(parent_key,'big'))%_N
    if child==0: raise ValueError("BIP32: child==0")
    return child.to_bytes(32,'big'),IR

def derive_address(seed, path_type, account=0, change=0, index=0):
    H=0x80000000
    purposes={"BIP84":84,"BIP49":49,"BIP44":44}
    p=purposes[path_type]
    raw=hmac_sha512(b"Bitcoin seed",seed); key,chain=raw[:32],raw[32:]
    for idx,hard in [(p+H,True),(H,True),(account+H,True),(change,False),(index,False)]:
        key,chain=ckd_priv(key,chain,idx,hard)
    pub=privkey_to_pubkey(key); h160=hash160(pub)
    if path_type=="BIP84":
        addr=bech32_encode("bc",h160)
    elif path_type=="BIP49":
        rs=b'\x00\x14'+h160; addr=base58check_encode(b'\x05'+hash160(rs))
    else:
        addr=base58check_encode(b'\x00'+h160)
    return addr, f"m/{p}'/0'/{account}'/{change}/{index}"

# ══════════════════════════════════════════════════════════════════════════
# BIP39 helpers
# ══════════════════════════════════════════════════════════════════════════
def entropy_to_mnemonic(entropy):
    assert len(entropy) in (16,20,24,28,32)
    eb=bin(int.from_bytes(entropy,'big'))[2:].zfill(len(entropy)*8)
    cs=len(entropy)*8//32
    csb=bin(sha256(entropy)[0])[2:].zfill(8)[:cs]
    full=eb+csb
    return " ".join(WORDLIST[int(full[i:i+11],2)] for i in range(0,len(full),11))

def mnemonic_to_seed(mnemonic, passphrase=""):
    m=unicodedata.normalize('NFKD',mnemonic.strip())
    s=unicodedata.normalize('NFKD',"mnemonic"+passphrase)
    return pbkdf2_hmac_sha512(m.encode('utf-8'),s.encode('utf-8'),2048,64)

def validate_mnemonic(mnemonic):
    words=mnemonic.strip().lower().split()
    if len(words) not in {12,15,18,21,24}: return False
    try: idxs=[WORDLIST.index(w) for w in words]
    except ValueError: return False
    bits=''.join(bin(i)[2:].zfill(11) for i in idxs)
    cs=len(words)*11//33
    ent=int(bits[:-cs],2).to_bytes(len(bits[:-cs])//8,'big')
    return bits[-cs:]==bin(sha256(ent)[0])[2:].zfill(8)[:cs]

def _validate_indices(indices):
    """Fast BIP39 checksum validation directly from WORDLIST indices (no string ops)."""
    n = len(indices)
    if n not in {12, 15, 18, 21, 24}:
        return False
    acc = 0
    for idx in indices:
        acc = (acc << 11) | idx
    total_bits = n * 11
    cs_bits = total_bits // 33
    ent_bits = total_bits - cs_bits
    ent = (acc >> cs_bits).to_bytes(ent_bits // 8, 'big')
    cs_got = acc & ((1 << cs_bits) - 1)
    cs_exp = sha256(ent)[0] >> (8 - cs_bits)
    return cs_got == cs_exp

# ══════════════════════════════════════════════════════════════════════════
# COMBO GENERATORS
# ══════════════════════════════════════════════════════════════════════════
def combos_asc(ranges):
    def _g(i,c):
        if i==len(ranges): yield tuple(c); return
        for v in range(ranges[i][0],ranges[i][1]+1):
            c.append(v); yield from _g(i+1,c); c.pop()
    yield from _g(0,[])

def combos_desc(ranges):
    def _g(i,c):
        if i==len(ranges): yield tuple(c); return
        for v in range(ranges[i][1],ranges[i][0]-1,-1):
            c.append(v); yield from _g(i+1,c); c.pop()
    yield from _g(0,[])

def _nxt_up(c,ranges):
    c=list(c)
    for i in range(len(c)-1,-1,-1):
        if c[i]<ranges[i][1]:
            c[i]+=1
            for j in range(i+1,len(c)): c[j]=ranges[j][0]
            return tuple(c)
        c[i]=ranges[i][0]
    return None

def _nxt_dn(c,ranges):
    c=list(c)
    for i in range(len(c)-1,-1,-1):
        if c[i]>ranges[i][0]:
            c[i]-=1
            for j in range(i+1,len(c)): c[j]=ranges[j][1]
            return tuple(c)
        c[i]=ranges[i][1]
    return None

def combos_exact_up(start,ranges):
    c=tuple(start)
    if any(not (lo <= v <= hi) for v, (lo, hi) in zip(c, ranges)):
        return
    while c: yield c; c=_nxt_up(c,ranges)

def combos_exact_dn(start,ranges):
    c=tuple(start)
    if any(not (lo <= v <= hi) for v, (lo, hi) in zip(c, ranges)):
        return
    while c: yield c; c=_nxt_dn(c,ranges)

# ══════════════════════════════════════════════════════════════════════════
# SELF-TESTS  (official BIP vectors)
# ══════════════════════════════════════════════════════════════════════════
def run_tests(silent=False):
    results=[]
    def chk(name,got,exp):
        p=(got==exp); results.append((name,p,got,exp)); return p
    chk("SHA-256 empty", sha256(b'').hex(),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    chk("SHA-256 abc", sha256(b'abc').hex(),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    chk("RIPEMD-160 empty", ripemd160(b'').hex(),
        "9c1185a5c5e9fc54612808977ee8f548b2258d31")
    chk("RIPEMD-160 abc", ripemd160(b'abc').hex(),
        "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc")
    raw=hmac_sha512(b"Bitcoin seed",bytes.fromhex("000102030405060708090a0b0c0d0e0f"))
    chk("BIP32 master priv", raw[:32].hex(),
        "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35")
    chk("BIP32 master chain", raw[32:].hex(),
        "873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508")
    mn="abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    sd=mnemonic_to_seed(mn,"")
    chk("BIP44 addr", derive_address(sd,"BIP44",0,0,0)[0], "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA")
    chk("BIP49 addr", derive_address(sd,"BIP49",0,0,0)[0], "37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf")
    chk("BIP84 addr", derive_address(sd,"BIP84",0,0,0)[0], "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")
    chk("BIP39 valid cs",  validate_mnemonic(mn), True)
    chk("BIP39 reject bad",validate_mnemonic("abandon "*11+"XXXXX"),False)
    passed=sum(1 for _,p,_,_ in results if p)
    failed=len(results)-passed
    if not silent:
        hdr("SELF-TEST — OFFICIAL BIP VECTORS")
        for name,p,got,exp in results:
            if p: ok(name)
            else:
                err(name)
                print(f"       exp: {exp}")
                print(f"       got: {got}")
        print()
        if failed==0:
            ok(f"All {passed} tests passed — crypto verified correct")
            if USE_COINCURVE:
                info("coincurve acceleration is ACTIVE")
            else:
                warn("coincurve not installed — using pure Python secp256k1 (slower)")
        else:
            err(f"{failed} test(s) FAILED — do not use for real keys")
    return failed==0

# ══════════════════════════════════════════════════════════════════════════
# VAULT  (JSON file — persistent memory with file-locking)
# ══════════════════════════════════════════════════════════════════════════
VAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallet_vault.json")

def vault_load():
    if not os.path.exists(VAULT_FILE): return []
    try:
        f = open(VAULT_FILE, 'r')
        _lock_file(f, exclusive=False)
        try:
            data = json.load(f)
        finally:
            _unlock_file(f)
            f.close()
        return data if isinstance(data, list) else []
    except Exception: return []

def vault_save(records):
    """Atomic vault write: serialise to a temp file beside the vault, then
    rename into place.  A crash during json.dump leaves the original intact."""
    tmp_path = VAULT_FILE + ".tmp"
    f = open(tmp_path, 'w')
    _lock_file(f, exclusive=True)
    try:
        json.dump(records, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    finally:
        _unlock_file(f)
        f.close()
    os.replace(tmp_path, VAULT_FILE)  # atomic on POSIX; best-effort on Windows

def vault_add(record):
    """Atomic read-modify-write with exclusive lock. Returns True if newly added.
    Uses 'a+' (create-if-missing, never truncates on open) so file creation
    happens under the same lock as the read — no TOCTOU race between threads/processes."""
    key = record.get("mnemonic", "").strip().lower()
    f = open(VAULT_FILE, 'a+')
    _lock_file(f, exclusive=True)
    try:
        f.seek(0)
        content = f.read()
        try: records = json.loads(content) if content.strip() else []
        except Exception: records = []
        if not isinstance(records, list): records = []
        for r in records:
            if r.get("mnemonic", "").strip().lower() == key:
                return False
        records.append(record)
        f.seek(0); f.truncate()
        json.dump(records, f, indent=2)
        f.flush(); os.fsync(f.fileno())
        return True
    finally:
        _unlock_file(f)
        f.close()

def vault_stats():
    records = vault_load()
    if not records: return {"total": 0, "addresses": 0, "first": "?", "last": "?"}
    dates = [r.get("timestamp","") for r in records if r.get("timestamp")]
    return {
        "total": len(records),
        "addresses": sum(len(r.get("addresses",[])) for r in records),
        "first": min(dates) if dates else "?",
        "last":  max(dates) if dates else "?",
    }

def _build_record(combo, mnemonic, seed_hex, addresses, note=""):
    return {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "combo":     list(combo),
        "mnemonic":  mnemonic,
        "seed_hex":  seed_hex,
        "addresses": addresses,
        "note":      note,
    }

def _derive_all_addresses(seed, account=0, change=0, count=3):
    out = []
    for pt in ["BIP84","BIP49","BIP44"]:
        for i in range(count):
            addr, path = derive_address(seed, pt, account, change, i)
            out.append({"type": pt, "path": path, "address": addr})
    return out

# ══════════════════════════════════════════════════════════════════════════
# CHECKPOINT helpers  (mnemonic hunt resume)
# ══════════════════════════════════════════════════════════════════════════
def _cand_lists_hash(cand_lists):
    return hashlib.sha256(str(cand_lists).encode()).hexdigest()

def save_hunt_checkpoint(filepath, rank, scanned, valid_count, dup_skipped, cand_lists,
                         word_count, passphrase, acct, change, addr_count, skip_dup,
                         total_raw, total_valid, part_mode, start_rank, stop_bound, step,
                         effective_valid_in_range=0, dup_free_frac=1.0):
    try:
        with open(filepath, 'w') as f:
            json.dump({
                "rank": rank, "scanned": scanned, "valid_count": valid_count,
                "dup_skipped": dup_skipped,
                "cand_lists_hash": _cand_lists_hash(cand_lists),
                "word_count": word_count, "passphrase": passphrase,
                "acct": acct, "change": change, "addr_count": addr_count,
                "skip_dup": skip_dup, "total_raw": total_raw, "total_valid": total_valid,
                "effective_valid_in_range": effective_valid_in_range,
                "dup_free_frac": dup_free_frac,
                "part_mode": part_mode, "start_rank": start_rank,
                "stop_bound": stop_bound, "step": step, "timestamp": time.time(),
            }, f)
    except Exception:
        pass

def load_hunt_checkpoint(filepath):
    if not os.path.exists(filepath): return None
    try:
        with open(filepath, 'r') as f: return json.load(f)
    except Exception: return None

def clear_hunt_checkpoint(filepath):
    try:
        if os.path.exists(filepath): os.remove(filepath)
    except Exception: pass

# ══════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════
def _addr_color(addr):
    if addr.startswith("bc1"): return BGRN
    if addr.startswith("3"):   return BYEL
    return BCYN

def print_addresses(addr_list):
    last_type = None
    for a in addr_list:
        if a["type"] != last_type:
            last_type = a["type"]
            purpose = {"BIP84":84,"BIP49":49,"BIP44":44}[a["type"]]
            print(f"\n  {CYAN}{'─'*4}{RESET} {BOLD}{a['type']}{RESET} "
                  f"{DIM}m/{purpose}'/0'/…{RESET}")
        c = _addr_color(a["address"])
        print(f"    {DIM}{a['path']:<28}{RESET}  {c}{a['address']}{RESET}")

def print_record(r, idx=None):
    ts   = r.get("timestamp","?")
    cmb  = r.get("combo",[])
    mn   = r.get("mnemonic","")
    note = r.get("note","")
    addrs= r.get("addresses",[])
    prefix = f"{BYEL}#{idx+1}{RESET}  " if idx is not None else ""
    print(f"\n{prefix}{CYAN}{'═'*68}{RESET}")
    print(f"  {DIM}Saved     :{RESET}  {ts}")
    if note: print(f"  {DIM}Note      :{RESET}  {BYEL}{note}{RESET}")
    if cmb:  print(f"  {DIM}Combo     :{RESET}  {list(cmb)}")
    words = mn.split()
    print(f"  {DIM}Mnemonic  :{RESET}")
    for i in range(0, len(words), 6):
        chunk = words[i:i+6]
        line = "  ".join(f"{BBLU}{i+j+1:>2}.{RESET}{w:<12}" for j,w in enumerate(chunk))
        print(f"    {line}")
    print_addresses(addrs)

# ══════════════════════════════════════════════════════════════════════════
# PROGRESS BAR helper  (used by hunt modes)
# ══════════════════════════════════════════════════════════════════════════
def _progress_bar(pct, width=20):
    """Return a filled progress bar string for a given percentage 0-100."""
    filled = int(width * pct / 100)
    bar_str = "█" * filled + "░" * (width - filled)
    return f"{BGRN}{bar_str}{RESET} {BYEL}{pct:6.2f}%{RESET}"

# ══════════════════════════════════════════════════════════════════════════
# ADDRESS DATABASE  (Bloom filter + set, mmap-loaded)
# ══════════════════════════════════════════════════════════════════════════
BRUTE_ADDR_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bruteaddress.txt"
)

class BloomFilter:
    __slots__ = ("_bits", "_m", "_k")
    def __init__(self, capacity: int, error_rate: float = 0.008):
        import math
        m = int(-capacity * math.log(error_rate) / (math.log(2) ** 2)) + 1
        self._m = m; self._k = 7
        self._bits = bytearray((m + 7) // 8)
    def _hashes(self, item: str):
        b = item.encode() if isinstance(item, str) else item
        d = hashlib.sha256(b).digest()
        h1 = int.from_bytes(d[:4],  'little')
        h2 = int.from_bytes(d[4:8], 'little') | 1
        for i in range(self._k): yield (h1 + i * h2) % self._m
    def add(self, item: str):
        bits = self._bits
        for pos in self._hashes(item): bits[pos >> 3] |= (1 << (pos & 7))
    def __contains__(self, item: str) -> bool:
        bits = self._bits
        for pos in self._hashes(item):
            if not (bits[pos >> 3] & (1 << (pos & 7))): return False
        return True
    @property
    def size_mb(self) -> float: return len(self._bits) / 1_048_576

class AddressDB:
    __slots__ = ("_set", "_bloom", "_count", "loaded", "path")
    def __init__(self):
        self._set: set = set(); self._bloom = None
        self._count = 0; self.loaded = False; self.path = BRUTE_ADDR_FILE
    def load(self, path=None):
        fpath = path or self.path
        if not os.path.exists(fpath): return 0, 0.0
        t0 = time.time()
        file_size = os.path.getsize(fpath)
        estimated_lines = max(file_size // 36, 1_000)
        print(f"  {BBLU}Loading {fpath}{RESET}")
        print(f"  {DIM}File size : {file_size/1_073_741_824:.3f} GB  "
              f"(~{estimated_lines:,} addresses estimated){RESET}")
        bloom = BloomFilter(estimated_lines, error_rate=0.008)
        addr_set: set = set()
        count = 0; report_every = 1_000_000; last_report = 0
        with open(fpath, 'rb') as f:
            mm = None
            try:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            except (mmap.error, ValueError):
                pass  # empty file or unsupported; fall back to normal file iteration
            try:
                if mm is not None:
                    # mmap supports readline(); do NOT iterate directly (yields bytes)
                    line_iter = iter(mm.readline, b'')
                else:
                    line_iter = f
                for raw_line in line_iter:
                    addr = raw_line.strip().decode('ascii', errors='ignore')
                    if not addr or addr.startswith('#'): continue
                    addr_set.add(addr); bloom.add(addr); count += 1
                    if count - last_report >= report_every:
                        last_report = count
                        elapsed_now = time.time() - t0
                        rate = count / elapsed_now if elapsed_now > 0 else 0
                        sys.stdout.write(
                            f"\r  {CYAN}⠿{RESET}  Loaded {count:>12,}  |  "
                            f"{rate/1e6:.2f}M/s  |  {elapsed_now:.0f}s elapsed   "
                        ); sys.stdout.flush()
            finally:
                if mm is not None: mm.close()
        sys.stdout.write("\r" + " " * 72 + "\r"); sys.stdout.flush()
        elapsed = time.time() - t0
        self._set = addr_set; self._bloom = bloom
        self._count = count; self.loaded = True; self.path = fpath
        return count, elapsed
    def __contains__(self, addr: str) -> bool:
        if self._bloom is None: return addr in self._set
        if addr not in self._bloom: return False
        return addr in self._set
    def __len__(self) -> int: return self._count
    @property
    def bloom_mb(self) -> float: return self._bloom.size_mb if self._bloom else 0.0

_ADDR_DB: AddressDB = AddressDB()

def ensure_addr_db_loaded(force_reload: bool = False) -> bool:
    if _ADDR_DB.loaded and not force_reload: return _ADDR_DB._count > 0
    fpath = BRUTE_ADDR_FILE
    if not os.path.exists(fpath):
        err(f"bruteaddress.txt not found at: {fpath}")
        warn("Create the file with one Bitcoin address per line.")
        return False
    section("Loading Address Database")
    info(f"File: {fpath}")
    info("This may take 1–3 min for large files. Loaded once per session.")
    print()
    count, elapsed = _ADDR_DB.load(fpath)
    if count == 0:
        err("File loaded but no valid addresses found."); return False
    rate = count / elapsed if elapsed > 0 else 0
    ok(f"Loaded {count:,} addresses in {elapsed:.1f}s  ({rate/1e6:.2f}M addr/s)")
    ok(f"Bloom filter: {_ADDR_DB.bloom_mb:.1f} MB  |  Set lookup: O(1)")
    return True

def addr_db_status() -> str:
    if not _ADDR_DB.loaded:
        return f"{BYEL}bruteaddress.txt: not loaded{RESET}"
    return (f"{BGRN}bruteaddress.txt: {_ADDR_DB._count:,} addresses loaded"
            f"  ({_ADDR_DB.bloom_mb:.0f} MB bloom){RESET}")

# ══════════════════════════════════════════════════════════════════════════
# MODE 1 — COMBO GENERATOR
# ══════════════════════════════════════════════════════════════════════════
def _int_prompt(msg, default):
    """Reusable integer prompt with validation."""
    while True:
        raw = prompt(msg, str(default))
        try: return int(raw)
        except ValueError: err("Please enter a whole number.")

def mode1_setup():
    clr(); hdr("MODE 1  —  COMBO GENERATOR")
    section("Combo Ranges  (one slot per line, format: min max)")
    info("Press Enter with no input to finish adding slots")

    DEFAULT_RANGES=[(4,42),(5,89),(4,61),(6,74),(4,55),(5,82),(5,67),(4,48)]
    use_def = yn("Use default 8-slot ranges "+str(DEFAULT_RANGES), "y")
    if use_def:
        ranges = DEFAULT_RANGES
    else:
        ranges = []
        for i in range(1,33):
            raw = prompt(f"Slot {i} (min max, blank=done)")
            if not raw: break
            parts = raw.split()
            if len(parts) != 2: err("Enter two numbers"); continue
            try:
                lo, hi = int(parts[0]), int(parts[1])
                if lo > hi: err(f"min ({lo}) > max ({hi}), skipped"); continue
                if hi > 255: warn(f"Slot {i}: max ({hi}) > 255 — will be byte-truncated")
                ranges.append((lo, hi))
            except ValueError: err("Not valid integers, skipped")
        if not ranges: err("No ranges entered"); press_enter(); return None

    section("Iteration Order")
    print(f"  {BYEL}1{RESET} Ascending   (min→max)")
    print(f"  {BYEL}2{RESET} Descending  (max→min)")
    print(f"  {BYEL}3{RESET} Exact combo only")
    print(f"  {BYEL}4{RESET} From exact combo upward")
    print(f"  {BYEL}5{RESET} From exact combo downward")
    order_map={"1":"asc","2":"desc","3":"exact","4":"exact_up","5":"exact_dn"}
    order = order_map.get(prompt("Choice","1"), "asc")

    exact_combo = None
    if order in ("exact","exact_up","exact_dn"):
        raw = prompt(f"Exact combo ({len(ranges)} values, comma-separated)",
                     ",".join(str(mn) for mn,_ in ranges))
        try:
            exact_combo = tuple(int(x.strip()) for x in raw.split(","))
            if len(exact_combo) != len(ranges):
                err("Wrong slot count"); press_enter(); return None
            for slot_i, (val,(lo,hi)) in enumerate(zip(exact_combo,ranges)):
                if not (lo <= val <= hi):
                    err(f"Slot {slot_i+1} value {val} is outside range [{lo},{hi}]")
                    press_enter(); return None
        except ValueError:
            err("Invalid numbers"); press_enter(); return None

    section("Settings")
    max_iter   = _int_prompt("Max iterations (0=unlimited)", 10)
    passphrase = prompt("BIP39 passphrase (blank=none)", "")
    acct       = _int_prompt("Account index", 0)
    change     = _int_prompt("Change index (0=external, 1=internal)", 0)
    addr_count = _int_prompt("Addresses per type", 3)
    save_vault = yn("Auto-save each result to vault", "n")

    return dict(ranges=ranges, order=order, exact_combo=exact_combo,
                max_iter=max_iter, passphrase=passphrase,
                acct=acct, change=change, addr_count=addr_count,
                save_vault=save_vault)

def run_mode1(cfg):
    ranges=cfg["ranges"]; order=cfg["order"]
    exact_combo=cfg.get("exact_combo")
    max_iter=cfg["max_iter"]; passphrase=cfg["passphrase"]
    acct=cfg["acct"]; change=cfg["change"]
    addr_count=cfg["addr_count"]; save_vault=cfg["save_vault"]

    if   order=="asc":      gen = combos_asc(ranges)
    elif order=="desc":     gen = combos_desc(ranges)
    elif order=="exact":    gen = iter([exact_combo])
    elif order=="exact_up": gen = combos_exact_up(exact_combo,ranges)
    else:                   gen = combos_exact_dn(exact_combo,ranges)

    clr(); hdr("MODE 1  —  GENERATING")
    count = 0; saved = 0
    try:
        for combo in gen:
            if max_iter and count >= max_iter: break
            count += 1
            cb       = bytes(v & 0xFF for v in combo)
            entropy  = sha256(cb)
            mnemonic = entropy_to_mnemonic(entropy)
            seed     = mnemonic_to_seed(mnemonic, passphrase)
            addrs    = _derive_all_addresses(seed, acct, change, addr_count)

            print(f"\n{CYAN}{'─'*76}{RESET}")
            print(f"  {BYEL}#{count}{RESET}  {DIM}combo{RESET} {list(combo)}  "
                  f"{DIM}entropy{RESET} {entropy.hex()[:16]}…")
            words = mnemonic.split()
            for i in range(0, len(words), 6):
                chunk = words[i:i+6]
                line = "  ".join(f"{BBLU}{i+j+1:>2}.{RESET}{w:<12}" for j,w in enumerate(chunk))
                print(f"    {line}")
            print_addresses(addrs)

            if save_vault:
                rec = _build_record(combo, mnemonic, seed.hex(), addrs)
                if vault_add(rec):
                    saved += 1
                    ok(f"Saved to vault (total {len(vault_load())})")
    except KeyboardInterrupt:
        print(f"\n{BYEL}  Interrupted.{RESET}")

    print(f"\n{CYAN}{'═'*76}{RESET}")
    ok(f"Generated {count} mnemonic(s).  Vault saves: {saved}")
    press_enter()

# ══════════════════════════════════════════════════════════════════════════
# MODE 3 — MNEMONIC VERIFY & DERIVE
# ══════════════════════════════════════════════════════════════════════════
def run_mode3():
    clr(); hdr("MODE 3  —  MNEMONIC VERIFY & DERIVE")
    section("Enter Mnemonic")
    info("Type or paste your BIP39 mnemonic (12/15/18/21/24 words)")
    raw = prompt("Mnemonic")
    if not raw: return

    mnemonic = raw.strip()
    words = mnemonic.split()
    print(f"\n  {DIM}Word count:{RESET} {len(words)}")

    section("Validation")
    valid = validate_mnemonic(mnemonic)
    if not valid:
        err("BIP39 checksum INVALID — check spelling/order"); press_enter(); return
    ok("BIP39 checksum VALID")

    passphrase = prompt("BIP39 passphrase (blank=none)", "")
    acct       = _int_prompt("Account index", 0)
    change     = _int_prompt("Change index (0=ext, 1=int)", 0)
    addr_count = _int_prompt("Addresses per type", 5)

    mnemonic = mnemonic.lower()
    seed = mnemonic_to_seed(mnemonic, passphrase)
    print(f"\n  {DIM}Seed (hex):{RESET}")
    sh = seed.hex()
    for i in range(0, len(sh), 64): print(f"    {DIM}{sh[i:i+64]}{RESET}")

    section("Derived Addresses")
    addrs = _derive_all_addresses(seed, acct, change, addr_count)
    print_addresses(addrs)

    section("Save to Vault?")
    if yn("Store this mnemonic + addresses in the vault","n"):
        note = prompt("Optional note (blank=none)","")
        rec = _build_record(tuple(), mnemonic, seed.hex(), addrs, note)
        if vault_add(rec): ok("Saved to vault")
        else: warn("Already in vault (duplicate mnemonic)")
    press_enter()

# ══════════════════════════════════════════════════════════════════════════
# HUNT MODE  —  scan combos vs bruteaddress.txt
# ══════════════════════════════════════════════════════════════════════════
def run_hunt():
    clr(); hdr("HUNT MODE  —  COMBO ADDRESS SCANNER")
    info("Targets loaded from  bruteaddress.txt  (one address per line)")
    info("Supports  bc1q… (BIP84)   3… (BIP49)   1… (BIP44)")
    print()
    if not ensure_addr_db_loaded(): press_enter(); return
    ok(f"Target DB ready: {len(_ADDR_DB):,} addresses"); print()

    section("Combo Ranges")
    DEFAULT_RANGES=[(4,42),(5,89),(4,61),(6,74),(4,55),(5,82),(5,67),(4,48)]
    use_def = yn("Use default ranges "+str(DEFAULT_RANGES), "y")
    ranges = DEFAULT_RANGES if use_def else []
    if not use_def:
        for i in range(1,33):
            raw = prompt(f"Slot {i} (min max, blank=done)","")
            if not raw: break
            p = raw.split()
            if len(p) == 2:
                try:
                    lo, hi = int(p[0]), int(p[1])
                    if lo > hi: err(f"Slot {i}: min>max, skipped"); continue
                    if hi > 255: warn(f"Slot {i}: max>255 — will be byte-truncated")
                    ranges.append((lo, hi))
                except ValueError: err(f"Slot {i}: not valid integers, skipped")
            else:
                err(f"Slot {i}: enter two integers separated by a space")
        if not ranges: err("No ranges."); press_enter(); return

    # Compute total combos for progress
    total_combos = 1
    for lo, hi in ranges: total_combos *= (hi - lo + 1)

    section("Scan Settings")
    print(f"  {BYEL}1{RESET} Ascending  {BYEL}2{RESET} Descending")
    order = {"1":"asc","2":"desc"}.get(prompt("Order","1"), "asc")
    passphrase = prompt("BIP39 passphrase (blank=none)","")
    acct       = _int_prompt("Account index", 0)
    change     = _int_prompt("Change index", 0)
    addr_count = _int_prompt("Addresses per type to check", 5)

    section(f"Hunt begins — {total_combos:,} combos total — Ctrl+C to abort")
    print()
    gen = combos_asc(ranges) if order=="asc" else combos_desc(ranges)
    found_records=[]; scanned=0; found_count=0; t0=time.time()
    addr_db=_ADDR_DB; derive_all=_derive_all_addresses
    build_record=_build_record; vault_add_fn=vault_add
    _eta = _EtaTracker()

    try:
        for combo in gen:
            scanned += 1
            cb       = bytes(v & 0xFF for v in combo)
            entropy  = sha256(cb)
            mnemonic = entropy_to_mnemonic(entropy)
            seed     = mnemonic_to_seed(mnemonic, passphrase)
            addrs    = derive_all(seed, acct, change, addr_count)
            for a in addrs:
                if a["address"] in addr_db:
                    spin("", done=True)
                    hit = a["address"]
                    print(f"\n  {BG_GRN}{BOLD}  ★ FOUND: {hit}  {RESET}")
                    print(f"  {DIM}combo    :{RESET} {list(combo)}")
                    print(f"  {DIM}path     :{RESET} {a['path']}")
                    print(f"  {DIM}type     :{RESET} {a['type']}")
                    rec = build_record(combo, mnemonic, seed.hex(), addrs,
                                       f"HUNT MATCH: {hit}")
                    if vault_add_fn(rec): ok(f"Auto-saved → combo {list(combo)}")
                    else: warn("Already in vault")
                    found_count += 1; found_records.append(hit)

            if scanned % 100 == 0:
                rate_str, eta_str = _eta.tick(scanned, total_combos)
                pct     = 100.0 * scanned / total_combos if total_combos > 0 else 0
                pbar    = _progress_bar(pct, width=18)
                spin(f"{pbar}  {scanned:,}/{total_combos:,}  {rate_str}  ETA {eta_str}  "
                     f"Matched {found_count}  Combo {list(combo)[:3]}…")
                check_pause_flag()
    except KeyboardInterrupt:
        spin("", done=True); warn("Hunt interrupted.")

    spin("", done=True)
    elapsed = time.time() - t0
    pct_done = 100.0 * scanned / total_combos if total_combos > 0 else 0
    print(f"\n  {DIM}Elapsed  :{RESET} {elapsed:.1f}s  "
          f"  {DIM}Scanned :{RESET} {scanned:,}/{total_combos:,}  "
          f"  {DIM}Progress:{RESET} {pct_done:.3f}%  "
          f"  {DIM}Found   :{RESET} {found_count}")
    if found_records:
        ok("Matched addresses auto-saved to vault.")
        for a in found_records: print(f"    {BGRN}★  {a}{RESET}")
    else:
        warn("No matches found in the scanned range.")
    press_enter()

# ══════════════════════════════════════════════════════════════════════════
# MNEMONIC HUNT HELPERS  (rank ↔ combo conversions)
# ══════════════════════════════════════════════════════════════════════════
def _parse_candidates(s):
    """Parse candidate spec → list of WORDLIST indices."""
    s = s.strip().lower()
    if s in ("all", ""):
        return list(range(2048))
    # Range like 0-100
    if re.fullmatch(r'\d+\s*-\s*\d+', s):
        try:
            a, b = s.split("-", 1)
            a, b = int(a.strip()), int(b.strip())
            if 0 <= a <= b < 2048:
                return list(range(a, b + 1))
            else:
                warn(f"Range '{s}' is inverted or out of bounds (must be 0 <= a <= b < 2048) — ignored")
        except ValueError:
            pass
    # Comma-separated words or indices
    parts = [p.strip() for p in s.split(",") if p.strip()]
    indices = []
    for p in parts:
        if p.isdigit():
            idx = int(p)
            if 0 <= idx < 2048: indices.append(idx)
        else:
            try: indices.append(WORDLIST.index(p))
            except ValueError: pass  # silently skip unknown words
    return indices if indices else list(range(2048))

def combo_to_index(combo, cand_lists):
    index = 0; multiplier = 1
    for i in range(len(cand_lists)-1, -1, -1):
        index += combo[i] * multiplier
        multiplier *= len(cand_lists[i])
    return index

def index_to_combo(index, cand_lists):
    combo = [0] * len(cand_lists); remaining = index
    for i in range(len(cand_lists)-1, -1, -1):
        sz = len(cand_lists[i])
        combo[i] = remaining % sz
        remaining //= sz
    return tuple(combo)

def next_combo(combo, lengths):
    combo = list(combo)
    for i in range(len(combo)-1, -1, -1):
        if combo[i] + 1 < lengths[i]:
            combo[i] += 1
            for j in range(i+1, len(combo)): combo[j] = 0
            return tuple(combo)
    return None

def prev_combo(combo, lengths):
    combo = list(combo)
    for i in range(len(combo)-1, -1, -1):
        if combo[i] > 0:
            combo[i] -= 1
            for j in range(i+1, len(combo)): combo[j] = lengths[j] - 1
            return tuple(combo)
    return None


# ══════════════════════════════════════════════════════════════════════════
# PERMUTATION HELPERS  (for mnemonic hunt R — permutation mode)
# ══════════════════════════════════════════════════════════════════════════
def _perm_count(n, k):
    """P(n,k) = n*(n-1)*...*(n-k+1) — number of k-permutations from n elements."""
    if k > n or k < 0: return 0
    if k == 0: return 1
    result = 1
    for i in range(n, n - k, -1):
        result *= i
    return result

def index_to_perm(index, pool_list, k):
    """Convert a 0-based rank index to a k-permutation of pool_list (lex order)."""
    pool = list(pool_list)
    n = len(pool)
    if k > n: return None
    perm = []
    remaining = index
    for i in range(k):
        picks_left = k - i
        m = len(pool)
        step = _perm_count(m - 1, picks_left - 1)
        if step < 1: step = 1
        chosen_idx = remaining // step
        if chosen_idx >= m: return None
        perm.append(pool[chosen_idx])
        pool.pop(chosen_idx)
        remaining %= step
    return tuple(perm)

def perm_to_index(perm, pool_list, k):
    """Convert a k-permutation back to its 0-based rank index."""
    pool = list(pool_list)
    index = 0
    for i in range(k):
        picks_left = k - i
        m = len(pool)
        step = _perm_count(m - 1, picks_left - 1)
        if step < 1: step = 1
        chosen_idx = pool.index(perm[i])
        index += chosen_idx * step
        pool.pop(chosen_idx)
    return index

# ══════════════════════════════════════════════════════════════════════════
# MNEMONIC HUNT  —  scan mnemonic patterns vs bruteaddress.txt
# ══════════════════════════════════════════════════════════════════════════
def run_mnemonic_hunt():
    clr(); hdr("MNEMONIC HUNT  —  PATTERN SCANNER")
    info("Enter a mnemonic pattern. Use '?' for unknown positions.")
    info("For unknown slots: provide words, indices, range (a-b), or 'all'.")
    info("Supports  bc1q… (BIP84)   3… (BIP49)   1… (BIP44)")
    print()
    if not ensure_addr_db_loaded(): press_enter(); return
    ok(f"Target DB ready: {len(_ADDR_DB):,} addresses"); print()

    section("Mnemonic Pattern")
    length_map = {"12":12,"15":15,"18":18,"21":21,"24":24}
    print(f"  {BYEL}12{RESET}  {BYEL}15{RESET}  {BYEL}18{RESET}  {BYEL}21{RESET}  {BYEL}24{RESET}")
    word_count = length_map.get(prompt("Word count","12"), 12)

    pattern = [None] * word_count
    unknown_slots = []   # [(position, [candidate_word_indices]), …]

    for i in range(word_count):
        w = prompt(f"Word {i+1} (word or '?')", "?").strip().lower()
        if w in ("?", ""):
            cs = prompt(f"  Candidates for slot {i+1} (words/idx/a-b/all)", "all")
            cands = _parse_candidates(cs)
            if not cands:
                warn(f"No valid candidates for slot {i+1} — using all 2048")
                cands = list(range(2048))
            unknown_slots.append((i, cands))
            info(f"    → {len(cands)} candidates for slot {i+1}")
        else:
            try:
                idx = WORDLIST.index(w)
                pattern[i] = idx
            except ValueError:
                err(f"'{w}' not in wordlist — treating as unknown")
                cs = prompt(f"  Candidates for word {i+1}", "all")
                cands = _parse_candidates(cs)
                if not cands:
                    warn(f"No valid candidates for slot {i+1} — using all 2048")
                    cands = list(range(2048))
                unknown_slots.append((i, cands))
                info(f"    → {len(cands)} candidates for slot {i+1}")

    if not unknown_slots:
        info("All words known — single-check mode")
        total_raw = 1; total_valid = 1; cand_lists = []
        _dup_free_frac = 1.0
    else:
        total_raw = 1; cand_lists = []
        for _, cands in unknown_slots:
            total_raw *= len(cands); cand_lists.append(cands)
        cs_bits = word_count * 11 // 33
        checksum_denom = 1 << cs_bits
        total_valid = max(1, total_raw // checksum_denom)

        # ── Dup-free fraction: P(all unknown draws are distinct words) ──
        # Geometric-mean pool size of the unknown candidate lists; known
        # fixed words are treated as pre-drawn from the shared 2048 pool.
        import math as _math
        n_known_fixed = word_count - len(unknown_slots)
        _log_sum = sum(_math.log(max(len(c), 1)) for c in cand_lists)
        _eff_pool = _math.exp(_log_sum / len(cand_lists))
        _eff_pool_adj = max(_eff_pool - n_known_fixed, len(cand_lists))
        _dup_free_frac = 1.0
        for _k in range(len(cand_lists)):
            _dup_free_frac *= max(0.0, (_eff_pool_adj - _k) / _eff_pool_adj)

        info(f"Total raw combinations  : {total_raw:,}")
        info(f"Checksum filter ({cs_bits} bits) : ~1/{checksum_denom} → ~{total_valid:,} valid seeds")

    # ──────────────────────────────────────────────────────────────────────────
    # Batch generate first N valid mnemonics (no address.txt dependency)
    # ──────────────────────────────────────────────────────────────────────────
    if yn("\nGenerate first N valid mnemonics from start (rank 1)?", "n"):
        try:
            n = int(prompt("How many valid mnemonics to generate?", "10"))
            if n <= 0:
                err("Number must be positive.")
            else:
                passphrase = prompt("BIP39 passphrase (blank=none)", "")
                acct       = _int_prompt("Account index", 0)
                change     = _int_prompt("Change index", 0)
                addr_count = _int_prompt("Addresses per type to check", 5)
                save_flag  = yn("Auto‑save each to vault?", "n")

                generated = 0
                rank = 1
                t0 = time.time()

                print(f"\n{CYAN}Generating first {n} valid mnemonics...{RESET}\n")

                while generated < n and rank <= total_raw:
                    idx = rank - 1
                    if unknown_slots:
                        combo = index_to_combo(idx, cand_lists)
                        for slot_idx, ((pos, _), ci) in enumerate(zip(unknown_slots, combo)):
                            pattern[pos] = cand_lists[slot_idx][ci]
                    # else pattern fully known, only rank 1 is valid

                    if _validate_indices(pattern):
                        generated += 1
                        words = [WORDLIST[i] for i in pattern]
                        mnemonic = " ".join(words)
                        seed = mnemonic_to_seed(mnemonic, passphrase)
                        addrs = _derive_all_addresses(seed, acct, change, addr_count)

                        # Always show the result (no dependency on address.txt)
                        print(f"\n{BOLD}{BYEL}Rank {rank} (valid #{generated}){RESET}")
                        print(f"  Mnemonic: {mnemonic}")
                        print_addresses(addrs)

                        # Optional: highlight if address is in bruteaddress.txt
                        # (Does NOT affect generation or saving)
                        for a in addrs:
                            if a["address"] in _ADDR_DB:
                                print(f"  {BG_RED}{BOLD}★ MATCH: {a['address']}{RESET}")
                                break

                        if save_flag:
                            note = f"Batch generated rank {rank}"
                            rec = _build_record((), mnemonic, seed.hex(), addrs, note)
                            if vault_add(rec):
                                ok("Saved to vault")
                            else:
                                warn("Duplicate or error")

                    rank += 1

                elapsed = time.time() - t0
                ok(f"Generated {generated} valid mnemonics in {elapsed:.1f}s")
                if generated < n:
                    warn(f"Only {generated} valid mnemonics exist in the whole space.")
                press_enter()
                return  # exit hunt mode after batch generation
        except ValueError:
            err("Invalid number.")

    section("Scan Settings")
    passphrase = prompt("BIP39 passphrase (blank=none)","")
    acct       = _int_prompt("Account index", 0)
    change     = _int_prompt("Change index (0=external, 1=internal)", 0)
    addr_count = _int_prompt("Addresses per type to check", 5)

    section("Duplicate Word Filter")
    skip_dup = yn("Skip mnemonics with duplicate words","n")

    if unknown_slots:
        if skip_dup:
            _dup_pct = _dup_free_frac * 100
            info(f"Dup-word filter          : keeps ~{_dup_pct:.2f}% → "
                 f"~{max(1, int(total_valid * _dup_free_frac)):,} valid seeds")
        if total_raw > 50_000_000_000:
            warn("Very large search space. Consider more known words.")
        if total_raw > 50_000_000:
            _eff_valid = max(1, int(total_valid * (_dup_free_frac if skip_dup else 1.0)))
            if not yn(f"Large space ({total_raw:,} raw / ~{_eff_valid:,} effective valid). Continue?","n"):
                return

    section("Scan Mode")
    print(f"  {BYEL}F{RESET} Full ascending    (scan the entire space: 0 → {total_raw-1:,})")
    print(f"  {BYEL}1{RESET} Custom range      (you choose the exact start/end ranks)")
    mode_sel = prompt("Select mode","F").strip().upper()
    start_rank = 0; stop_bound = total_raw; step = 1; part_desc = "full ascending"
    mode_choice = "F"; range_tag = "full"

    if mode_sel == "1":
        print(f"\n  Total ranks available: 0 → {total_raw-1:,}")
        info("Tip: End = 0 means 'scan all the way to the end'")
        raw_start = _int_prompt("Start rank", 0)
        raw_end   = _int_prompt("End rank (exclusive, 0 = scan to the end)", 0)
        if raw_start < 0: raw_start = 0
        if raw_end <= 0 or raw_end > total_raw: raw_end = total_raw
        if raw_start >= raw_end:
            warn("Start >= End — defaulting to full scan")
        else:
            mode_choice = "1"
            start_rank = raw_start; stop_bound = raw_end; step = 1
            part_desc  = f"custom range {raw_start:,} → {raw_end-1:,}"
            range_tag  = f"{raw_start}_{raw_end}"

    checkpoint_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"hunt_checkpoint_{range_tag}.json"
    )

    info(f"Scan mode: {part_desc}")
    section("Hunt begins — press Ctrl+C to abort / save checkpoint")
    print()

    # ── checkpoint resume ──
    found_records=[]; scanned=0; valid_count=0; found_count=0; dup_skipped=0
    effective_valid_in_range = 0  # 0 = not yet computed; set by checkpoint or calc below
    t0=time.time(); current_rank=start_rank
    CHECKPOINT_INTERVAL=500_000; last_checkpoint_save=0
    _eta = _EtaTracker()

    cp = load_hunt_checkpoint(checkpoint_file)
    if cp is not None:
        if (cp.get("cand_lists_hash") == _cand_lists_hash(cand_lists) and
            cp.get("word_count")   == word_count   and
            cp.get("passphrase")   == passphrase    and
            cp.get("acct")         == acct          and
            cp.get("change")       == change        and
            cp.get("addr_count")   == addr_count    and
            cp.get("skip_dup")     == skip_dup      and
            cp.get("total_raw")    == total_raw     and
            cp.get("part_mode")    == mode_choice   and
            cp.get("start_rank")   == start_rank    and
            cp.get("stop_bound")   == stop_bound    and
            cp.get("step")         == step):
            if yn(f"Checkpoint found at rank {cp['rank']:,}. Resume?","y"):
                current_rank = cp["rank"]
                scanned      = cp["scanned"]
                valid_count  = cp["valid_count"]
                dup_skipped  = cp["dup_skipped"]
                # restore effective denominator if saved (fallback to freshly computed)
                if cp.get("effective_valid_in_range"):
                    effective_valid_in_range = cp["effective_valid_in_range"]
                info(f"Resuming from rank {current_rank:,} "
                     f"(scanned {scanned:,}, valid {valid_count:,})")
            else:
                clear_hunt_checkpoint(checkpoint_file)
        else:
            warn("Checkpoint mismatch — starting fresh.")
            clear_hunt_checkpoint(checkpoint_file)

    # ── cache locals for speed ──
    addr_db=_ADDR_DB; derive_all=_derive_all_addresses
    build_record=_build_record; vault_add_fn=vault_add

    # ── Effective search space: partition → checksum → dup filter ──
    # raw partition size
    if step == 1:
        range_size = stop_bound - start_rank
    else:
        range_size = start_rank - stop_bound  # descending

    # fraction of total_raw covered by this partition
    _part_frac   = range_size / total_raw if total_raw > 0 else 1.0

    # effective valid seeds inside this partition after all filters
    _dup_frac    = _dup_free_frac if (skip_dup and unknown_slots) else 1.0
    _cs_frac     = 1.0 / (1 << (word_count * 11 // 33)) if unknown_slots else 1.0
    # effective_valid_in_range is the denominator for valid-% progress
    # Only compute if not already restored from a checkpoint (checkpoint wins)
    if not effective_valid_in_range:
        effective_valid_in_range = max(1, int(total_raw * _part_frac * _cs_frac * _dup_frac))

    try:
        if not unknown_slots:
            # ── single-check mode ──
            if _validate_indices(pattern):
                valid_count = 1
                words_now   = [WORDLIST[i] for i in pattern]
                mnemonic    = " ".join(words_now)
                seed        = mnemonic_to_seed(mnemonic, passphrase)
                addrs       = derive_all(seed, acct, change, addr_count)
                for a in addrs:
                    if a["address"] in addr_db:
                        hit = a["address"]
                        print(f"\n  {BG_GRN}{BOLD}  ★ FOUND: {hit}  {RESET}")
                        print(f"  {DIM}mnemonic :{RESET} {mnemonic}")
                        print(f"  {DIM}path     :{RESET} {a['path']}")
                        rec = build_record((), mnemonic, seed.hex(), addrs,
                                           f"MNEMONIC HUNT MATCH: {hit}")
                        if vault_add_fn(rec): ok("Auto-saved to vault")
                        found_count += 1; found_records.append(hit)
            scanned = 1
        else:
            # ── rank-based iteration ──
            words_cur = ["?", "?"]
            while True:
                if step == 1  and current_rank >= stop_bound: break
                if step == -1 and current_rank <= stop_bound: break

                scanned += 1
                combo = index_to_combo(current_rank, cand_lists)

                # Fill unknown slots into pattern
                for slot_idx, ((pos, _), idx) in enumerate(zip(unknown_slots, combo)):
                    pattern[pos] = cand_lists[slot_idx][idx]

                # Duplicate-word filter
                if skip_dup and len(set(pattern)) != len(pattern):
                    dup_skipped += 1
                else:
                    if _validate_indices(pattern):
                        valid_count += 1
                        words_cur   = [WORDLIST[i] for i in pattern]
                        mnemonic    = " ".join(words_cur)
                        seed        = mnemonic_to_seed(mnemonic, passphrase)
                        addrs       = derive_all(seed, acct, change, addr_count)

                        for a in addrs:
                            if a["address"] in addr_db:
                                spin("", done=True)
                                hit = a["address"]
                                print(f"\n  {BG_GRN}{BOLD}  ★ FOUND: {hit}  {RESET}")
                                print(f"  {DIM}mnemonic :{RESET} {mnemonic}")
                                print(f"  {DIM}path     :{RESET} {a['path']}")
                                print(f"  {DIM}type     :{RESET} {a['type']}")
                                rec = build_record((), mnemonic, seed.hex(), addrs,
                                                   f"MNEMONIC HUNT MATCH: {hit}")
                                if vault_add_fn(rec): ok("Auto-saved to vault")
                                else: warn("Already in vault")
                                hunt_log_match("M", mnemonic, addrs, rank=current_rank)
                                found_count += 1; found_records.append(hit)
                        # Reset display words after each valid check
                        words_cur = ["?","?"]

                # ── progress spinner with ETA ──
                if scanned % 500 == 0:
                    ranks_done = abs(current_rank - start_rank)
                    rate_str, eta_str = _eta.tick(ranks_done, range_size)
                    dup_str = f"Dup↓{dup_skipped:,}  " if skip_dup and dup_skipped else ""
                    pct_part  = 100.0 * ranks_done / range_size if range_size > 0 else 0
                    pct_valid = (100.0 * valid_count / effective_valid_in_range
                                 if effective_valid_in_range > 0 else 0)
                    pbar = _progress_bar(pct_part, width=16)
                    spin(
                        f"{pbar}  "
                        f"Raw {scanned:,}/{range_size:,}  "
                        f"Valid {valid_count:,}({pct_valid:.4f}%)  "
                        f"{dup_str}"
                        f"{rate_str}  ETA {eta_str}  "
                        f"Hits {found_count}"
                    )
                    check_pause_flag()

                # ── checkpoint save ──
                if scanned - last_checkpoint_save >= CHECKPOINT_INTERVAL:
                    last_checkpoint_save = scanned
                    save_hunt_checkpoint(
                        checkpoint_file, current_rank, scanned, valid_count,
                        dup_skipped, cand_lists, word_count, passphrase, acct,
                        change, addr_count, skip_dup, total_raw, total_valid,
                        mode_choice, start_rank, stop_bound, step,
                        effective_valid_in_range, _dup_free_frac)

                current_rank += step

    except KeyboardInterrupt:
        spin("", done=True)
        warn("Hunt interrupted. Saving checkpoint…")
        save_hunt_checkpoint(
            checkpoint_file, current_rank, scanned, valid_count, dup_skipped,
            cand_lists, word_count, passphrase, acct, change, addr_count,
            skip_dup, total_raw, total_valid, mode_choice, start_rank, stop_bound, step,
            effective_valid_in_range, _dup_free_frac)
        elapsed = time.time() - t0
        ranks_done = abs(current_rank - start_rank)
        pct_done   = 100.0 * ranks_done / range_size if range_size > 0 else 0
        pct_valid  = (100.0 * valid_count / effective_valid_in_range
                      if effective_valid_in_range > 0 else 0)
        print(f"\n  {DIM}Saved checkpoint."
              f"  Progress: {pct_done:.3f}% of partition"
              f"  |  Valid: {valid_count:,} ({pct_valid:.4f}% of ~{effective_valid_in_range:,} expected){RESET}")
        hunt_log_session("M", scanned, valid_count, found_count, elapsed)
        try: press_enter()
        except _HomeSignal: raise
        return

    # ── normal completion ──
    clear_hunt_checkpoint(checkpoint_file)
    spin("", done=True)
    elapsed = time.time() - t0
    pct_valid_final = (100.0 * valid_count / effective_valid_in_range
                       if effective_valid_in_range > 0 else 0)
    dup_msg = f"  {DIM}DupSkip:{RESET} {dup_skipped:,}  " if skip_dup and dup_skipped else ""
    print(f"\n  {DIM}Elapsed :{RESET} {elapsed:.1f}s  "
          f"  {DIM}Scanned :{RESET} {scanned:,}  "
          f"{dup_msg}"
          f"  {DIM}Valid   :{RESET} {valid_count:,} ({pct_valid_final:.4f}% of ~{effective_valid_in_range:,} expected)  "
          f"  {DIM}Found   :{RESET} {found_count}")
    hunt_log_session("M", scanned, valid_count, found_count, elapsed)
    if found_records:
        ok("Matched addresses auto-saved to vault.")
        for a in found_records: print(f"    {BGRN}★  {a}{RESET}")
    else:
        warn("No matches found in the scanned range.")
    try: press_enter()
    except _HomeSignal: raise


# ══════════════════════════════════════════════════════════════════════════
# MNEMONIC HUNT R  —  scan mnemonic patterns (PERMUTATION MODE) vs bruteaddress.txt
# ══════════════════════════════════════════════════════════════════════════
def run_mnemonic_hunt_permutation():
    clr(); hdr("MNEMONIC HUNT R  —  PERMUTATION SCANNER")
    info("Enter a mnemonic pattern. Use '?' for unknown positions.")
    info("For unknown slots: provide words, indices, range (a-b), or 'all'.")
    info("Supports  bc1q\u2026 (BIP84)   3\u2026 (BIP49)   1\u2026 (BIP44)")
    info("Permutation mode: each word drawn WITHOUT replacement across unknown slots.")
    print()
    if not ensure_addr_db_loaded(): press_enter(); return
    ok(f"Target DB ready: {len(_ADDR_DB):,} addresses"); print()

    section("Mnemonic Pattern")
    length_map = {"12":12,"15":15,"18":18,"21":21,"24":24}
    print(f"  {BYEL}12{RESET}  {BYEL}15{RESET}  {BYEL}18{RESET}  {BYEL}21{RESET}  {BYEL}24{RESET}")
    word_count = length_map.get(prompt("Word count","12"), 12)

    pattern = [None] * word_count
    unknown_slots = []   # [(position, [candidate_word_indices]), ...]

    for i in range(word_count):
        w = prompt(f"Word {i+1} (word or '?')", "?").strip().lower()
        if w in ("?", ""):
            cs = prompt(f"  Candidates for slot {i+1} (words/idx/a-b/all)", "all")
            cands = _parse_candidates(cs)
            if not cands:
                warn(f"No valid candidates for slot {i+1} — using all 2048")
                cands = list(range(2048))
            unknown_slots.append((i, cands))
            info(f"    → {len(cands)} candidates for slot {i+1}")
        else:
            try:
                idx = WORDLIST.index(w)
                pattern[i] = idx
            except ValueError:
                err(f"\'{w}\' not in wordlist — treating as unknown")
                cs = prompt(f"  Candidates for word {i+1}", "all")
                cands = _parse_candidates(cs)
                if not cands:
                    warn(f"No valid candidates for slot {i+1} — using all 2048")
                    cands = list(range(2048))
                unknown_slots.append((i, cands))
                info(f"    → {len(cands)} candidates for slot {i+1}")

    if not unknown_slots:
        info("All words known — single-check mode")
        cand_lists = []; pool = []; n_unknown = 0
        total_raw = 1; total_valid = 1
        _dup_free_frac = 1.0
    else:
        # Build shared permutation pool: union of all candidates
        pool_set = set()
        cand_lists = []
        for _, cands in unknown_slots:
            pool_set.update(cands)
            cand_lists.append(cands)
        pool = sorted(pool_set)
        n_unknown = len(unknown_slots)
        pool_size = len(pool)

        total_raw = _perm_count(pool_size, n_unknown)
        if total_raw == 0:
            err(f"Pool too small: {pool_size} unique candidates cannot fill "
                f"{n_unknown} unknown slots without repetition.")
            err("Add more candidate words, widen ranges, or use 'all' for some slots.")
            press_enter(); return
        cs_bits = word_count * 11 // 33
        checksum_denom = 1 << cs_bits
        total_valid = max(1, total_raw // checksum_denom)
        # Permutations are inherently dup-free across unknown slots
        _dup_free_frac = 1.0

        info(f"Permutation pool size   : {pool_size:,} unique candidates")
        info(f"Unknown slots           : {n_unknown}")
        info(f"Total raw permutations  : {total_raw:,}")
        info(f"Checksum filter ({cs_bits} bits) : ~1/{checksum_denom} → ~{total_valid:,} valid seeds")
        info("Note: permutation mode inherently prevents duplicate words across unknown slots.")

    # Precompute candidate sets for fast slot-compatibility checking
    cand_sets = [set(cands) for _, cands in unknown_slots]

    # ── Estimate slot-compatible steps (permutations that pass the candidate filter) ──
    # For each slot i: P(pass | i slots consumed) = min(|cand_set[i]|, pool-i) / (pool-i)
    # Product across all slots gives the fraction of raw perms that are slot-compatible.
    def _compute_compat_steps(pool_sz, cand_set_list, raw_total):
        if not cand_set_list or pool_sz == 0:
            return max(1, raw_total)
        frac = 1.0
        for i, cs in enumerate(cand_set_list):
            remaining = pool_sz - i
            if remaining <= 0:
                return 0
            frac *= min(len(cs), remaining) / remaining
        return max(1, int(raw_total * frac))

    _compat_steps_total = (_compute_compat_steps(
        len(pool), cand_sets, total_raw
    ) if unknown_slots else 1)

    # ──────────────────────────────────────────────────────────────────────────
    # Batch generate first N valid mnemonics (no address.txt dependency)
    # ──────────────────────────────────────────────────────────────────────────
    if yn("\nGenerate first N valid mnemonics from start (rank 1)?", "n"):
        try:
            n = int(prompt("How many valid mnemonics to generate?", "10"))
            if n <= 0:
                err("Number must be positive.")
            else:
                passphrase = prompt("BIP39 passphrase (blank=none)", "")
                acct       = _int_prompt("Account index", 0)
                change     = _int_prompt("Change index", 0)
                addr_count = _int_prompt("Addresses per type to check", 5)
                save_flag  = yn("Auto\u2011save each to vault?", "n")

                generated = 0
                rank = 0   # 0-based
                t0 = time.time()

                print(f"\n{CYAN}Generating first {n} valid mnemonics (permutation mode)...{RESET}\n")

                while generated < n and rank < total_raw:
                    perm = index_to_perm(rank, pool, n_unknown)
                    if perm is not None:
                        slot_ok = all(perm[i] in cand_sets[i] for i in range(n_unknown))
                        if slot_ok:
                            pat_copy = list(pattern)
                            for slot_idx, ((pos, _), val) in enumerate(zip(unknown_slots, perm)):
                                pat_copy[pos] = val
                            if _validate_indices(pat_copy):
                                generated += 1
                                words = [WORDLIST[i] for i in pat_copy]
                                mnemonic = " ".join(words)
                                seed = mnemonic_to_seed(mnemonic, passphrase)
                                addrs = _derive_all_addresses(seed, acct, change, addr_count)

                                print(f"\n{BOLD}{BYEL}Rank {rank+1} (valid #{generated}){RESET}")
                                print(f"  Mnemonic: {mnemonic}")
                                print_addresses(addrs)

                                for a in addrs:
                                    if a["address"] in _ADDR_DB:
                                        print(f"  {BG_RED}{BOLD}\u2605 MATCH: {a['address']}{RESET}")
                                        break

                                if save_flag:
                                    note = f"Perm batch generated rank {rank+1}"
                                    rec = _build_record((), mnemonic, seed.hex(), addrs, note)
                                    if vault_add(rec):
                                        ok("Saved to vault")
                                    else:
                                        warn("Duplicate or error")
                    rank += 1

                elapsed = time.time() - t0
                ok(f"Generated {generated} valid mnemonics in {elapsed:.1f}s")
                if generated < n:
                    warn(f"Only {generated} valid mnemonics exist in the whole space.")
                press_enter()
                return
        except ValueError:
            err("Invalid number.")

    section("Scan Settings")
    passphrase = prompt("BIP39 passphrase (blank=none)","")
    acct       = _int_prompt("Account index", 0)
    change     = _int_prompt("Change index (0=external, 1=internal)", 0)
    addr_count = _int_prompt("Addresses per type to check", 5)

    section("Duplicate Word Filter")
    info("Permutation mode already prevents repeats across unknown slots.")
    info("This filter additionally skips if any unknown word matches a known/fixed slot word.")
    skip_dup = yn("Skip mnemonics with duplicate words (across full mnemonic)","n")

    if unknown_slots:
        if total_raw > 50_000_000_000:
            warn("Very large search space. Consider more known words.")
        if total_raw > 50_000_000:
            if not yn(f"Large space ({total_raw:,} raw perms / ~{total_valid:,} expected valid). Continue?","n"):
                return

    section("Scan Mode")
    print(f"  {BYEL}F{RESET} Full ascending    (scan the entire space: 0 → {total_raw-1:,})")
    print(f"  {BYEL}1{RESET} Custom range      (you choose the exact start/end ranks)")
    mode_sel = prompt("Select mode","F").strip().upper()
    start_rank = 0; stop_bound = total_raw; step = 1; part_desc = "full ascending"
    mode_choice = "F"; range_tag = "full"

    if mode_sel == "1":
        print(f"\n  Total ranks available: 0 → {total_raw-1:,}")
        info("Tip: End = 0 means 'scan all the way to the end'")
        raw_start = _int_prompt("Start rank", 0)
        raw_end   = _int_prompt("End rank (exclusive, 0 = scan to the end)", 0)
        if raw_start < 0: raw_start = 0
        if raw_end <= 0 or raw_end > total_raw: raw_end = total_raw
        if raw_start >= raw_end:
            warn("Start >= End — defaulting to full scan")
        else:
            mode_choice = "1"
            start_rank = raw_start; stop_bound = raw_end; step = 1
            part_desc  = f"custom range {raw_start:,} → {raw_end-1:,}"
            range_tag  = f"{raw_start}_{raw_end}"

    checkpoint_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"hunt_perm_checkpoint_{range_tag}.json"
    )

    info(f"Scan mode: {part_desc}")
    section("Hunt begins — press Ctrl+C to abort / save checkpoint")
    print()

    # ── checkpoint resume ──
    found_records=[]; scanned=0; valid_count=0; found_count=0; dup_skipped=0; slot_ok_count=0
    effective_valid_in_range = 0
    t0=time.time(); current_rank=start_rank
    CHECKPOINT_INTERVAL=500_000; last_checkpoint_save=0
    _eta = _EtaTracker()

    _pool_hash_key = [pool]   # wrap pool in list so _cand_lists_hash works on it
    cp = load_hunt_checkpoint(checkpoint_file)
    if cp is not None:
        if (cp.get("cand_lists_hash") == _cand_lists_hash(_pool_hash_key) and
            cp.get("word_count")   == word_count   and
            cp.get("passphrase")   == passphrase    and
            cp.get("acct")         == acct          and
            cp.get("change")       == change        and
            cp.get("addr_count")   == addr_count    and
            cp.get("skip_dup")     == skip_dup      and
            cp.get("total_raw")    == total_raw     and
            cp.get("part_mode")    == mode_choice   and
            cp.get("start_rank")   == start_rank    and
            cp.get("stop_bound")   == stop_bound    and
            cp.get("step")         == step):
            if yn(f"Checkpoint found at rank {cp['rank']:,}. Resume?","y"):
                current_rank = cp["rank"]
                scanned      = cp["scanned"]
                valid_count  = cp["valid_count"]
                dup_skipped  = cp["dup_skipped"]
                if cp.get("effective_valid_in_range"):
                    effective_valid_in_range = cp["effective_valid_in_range"]
                info(f"Resuming from rank {current_rank:,} "
                     f"(scanned {scanned:,}, valid {valid_count:,})")
            else:
                clear_hunt_checkpoint(checkpoint_file)
        else:
            warn("Checkpoint mismatch — starting fresh.")
            clear_hunt_checkpoint(checkpoint_file)

    # ── cache locals for speed ──
    addr_db=_ADDR_DB; derive_all=_derive_all_addresses
    build_record=_build_record; vault_add_fn=vault_add

    # ── Effective search space ──
    if step == 1:
        range_size = stop_bound - start_rank
    else:
        range_size = start_rank - stop_bound

    _part_frac = range_size / total_raw if total_raw > 0 else 1.0
    _cs_frac   = 1.0 / (1 << (word_count * 11 // 33)) if unknown_slots else 1.0

    if not effective_valid_in_range:
        effective_valid_in_range = max(1, int(total_raw * _part_frac * _cs_frac))

    try:
        if not unknown_slots:
            # ── single-check mode ──
            if _validate_indices(pattern):
                valid_count = 1
                words_now   = [WORDLIST[i] for i in pattern]
                mnemonic    = " ".join(words_now)
                seed        = mnemonic_to_seed(mnemonic, passphrase)
                addrs       = derive_all(seed, acct, change, addr_count)
                for a in addrs:
                    if a["address"] in addr_db:
                        hit = a["address"]
                        print(f"\n  {BG_GRN}{BOLD}  \u2605 FOUND: {hit}  {RESET}")
                        print(f"  {DIM}mnemonic :{RESET} {mnemonic}")
                        print(f"  {DIM}path     :{RESET} {a['path']}")
                        rec = build_record((), mnemonic, seed.hex(), addrs,
                                           f"MNEMONIC HUNT R MATCH: {hit}")
                        if vault_add_fn(rec): ok("Auto-saved to vault")
                        found_count += 1; found_records.append(hit)
            scanned = 1
        else:
            # ── permutation rank-based iteration ──
            while True:
                if step == 1  and current_rank >= stop_bound: break
                if step == -1 and current_rank <= stop_bound: break

                scanned += 1
                perm = index_to_perm(current_rank, pool, n_unknown)

                if perm is not None:
                    # Slot-compatibility check
                    slot_ok = all(perm[i] in cand_sets[i] for i in range(n_unknown))
                    if slot_ok:
                        slot_ok_count += 1
                        pat_copy = list(pattern)
                        for slot_idx, ((pos, _), val) in enumerate(zip(unknown_slots, perm)):
                            pat_copy[pos] = val

                        # Duplicate-word filter (full mnemonic, including fixed slots)
                        if skip_dup and len(set(pat_copy)) != len(pat_copy):
                            dup_skipped += 1
                        else:
                            if _validate_indices(pat_copy):
                                valid_count += 1
                                words_cur   = [WORDLIST[i] for i in pat_copy]
                                mnemonic    = " ".join(words_cur)
                                seed        = mnemonic_to_seed(mnemonic, passphrase)
                                addrs       = derive_all(seed, acct, change, addr_count)

                                for a in addrs:
                                    if a["address"] in addr_db:
                                        spin("", done=True)
                                        hit = a["address"]
                                        print(f"\n  {BG_GRN}{BOLD}  \u2605 FOUND: {hit}  {RESET}")
                                        print(f"  {DIM}mnemonic :{RESET} {mnemonic}")
                                        print(f"  {DIM}path     :{RESET} {a['path']}")
                                        print(f"  {DIM}type     :{RESET} {a['type']}")
                                        rec = build_record((), mnemonic, seed.hex(), addrs,
                                                           f"MNEMONIC HUNT R MATCH: {hit}")
                                        if vault_add_fn(rec): ok("Auto-saved to vault")
                                        else: warn("Already in vault")
                                        hunt_log_match("R", mnemonic, addrs, rank=current_rank)
                                        found_count += 1; found_records.append(hit)

                # ── progress spinner: permutation mode shows slot-compat steps ──
                # "Steps" = how many permutations actually passed the slot filter
                # (these are the real work units; raw rank skips are invisible noise)
                if scanned % 500 == 0:
                    _compat_in_range = max(1, int(_compat_steps_total * _part_frac))
                    rate_str, eta_str = _eta.tick(slot_ok_count, _compat_in_range)
                    dup_str = f"Dup↓{dup_skipped:,}  " if skip_dup and dup_skipped else ""
                    pct_compat = (100.0 * slot_ok_count / _compat_in_range
                                  if _compat_in_range > 0 else 0)
                    pct_valid  = (100.0 * valid_count / effective_valid_in_range
                                  if effective_valid_in_range > 0 else 0)
                    pbar = _progress_bar(pct_compat, width=16)
                    spin(
                        f"{pbar}  "
                        f"Steps {slot_ok_count:,}/~{_compat_in_range:,}({pct_compat:.2f}%)  "
                        f"Valid {valid_count:,}({pct_valid:.4f}%)  "
                        f"{dup_str}"
                        f"{rate_str}  ETA {eta_str}  "
                        f"Hits {found_count}"
                    )
                    check_pause_flag()

                # ── checkpoint save ──
                if scanned - last_checkpoint_save >= CHECKPOINT_INTERVAL:
                    last_checkpoint_save = scanned
                    save_hunt_checkpoint(
                        checkpoint_file, current_rank, scanned, valid_count,
                        dup_skipped, _pool_hash_key, word_count, passphrase, acct,
                        change, addr_count, skip_dup, total_raw, total_valid,
                        mode_choice, start_rank, stop_bound, step,
                        effective_valid_in_range, _dup_free_frac)

                current_rank += step

    except KeyboardInterrupt:
        spin("", done=True)
        warn("Hunt interrupted. Saving checkpoint…")
        save_hunt_checkpoint(
            checkpoint_file, current_rank, scanned, valid_count, dup_skipped,
            _pool_hash_key, word_count, passphrase, acct, change, addr_count,
            skip_dup, total_raw, total_valid, mode_choice, start_rank, stop_bound, step,
            effective_valid_in_range, _dup_free_frac)
        elapsed = time.time() - t0
        ranks_done = abs(current_rank - start_rank)
        pct_done   = 100.0 * ranks_done / range_size if range_size > 0 else 0
        pct_valid  = (100.0 * valid_count / effective_valid_in_range
                      if effective_valid_in_range > 0 else 0)
        print(f"\n  {DIM}Saved checkpoint."
              f"  Progress: {pct_done:.3f}% of partition"
              f"  |  Valid: {valid_count:,} ({pct_valid:.4f}% of ~{effective_valid_in_range:,} expected){RESET}")
        hunt_log_session("R", scanned, valid_count, found_count, elapsed)
        try: press_enter()
        except _HomeSignal: raise
        return

    # ── normal completion ──
    clear_hunt_checkpoint(checkpoint_file)
    spin("", done=True)
    elapsed = time.time() - t0
    pct_valid_final = (100.0 * valid_count / effective_valid_in_range
                       if effective_valid_in_range > 0 else 0)
    dup_msg = f"  {DIM}DupSkip:{RESET} {dup_skipped:,}  " if skip_dup and dup_skipped else ""
    print(f"\n  {DIM}Elapsed :{RESET} {elapsed:.1f}s  "
          f"  {DIM}Scanned :{RESET} {scanned:,}  "
          f"{dup_msg}"
          f"  {DIM}Valid   :{RESET} {valid_count:,} ({pct_valid_final:.4f}% of ~{effective_valid_in_range:,} expected)  "
          f"  {DIM}Found   :{RESET} {found_count}")
    hunt_log_session("R", scanned, valid_count, found_count, elapsed)
    if found_records:
        ok("Matched addresses auto-saved to vault.")
        for a in found_records: print(f"    {BGRN}\u2605  {a}{RESET}")
    else:
        warn("No matches found in the scanned range.")
    try: press_enter()
    except _HomeSignal: raise

# ══════════════════════════════════════════════════════════════════════════
# VAULT BROWSER
# ══════════════════════════════════════════════════════════════════════════
def vault_browser():
    while True:
        clr(); hdr("VAULT BROWSER  —  PERSISTENT MEMORY")
        records = vault_load()
        st = vault_stats()
        if st["total"] == 0:
            warn("Vault is empty. Use Hunt or Combo Generator to populate it.")
            press_enter(); return
        print(f"\n  {DIM}Vault file :{RESET} {VAULT_FILE}")
        print(f"  {DIM}Records    :{RESET} {BYEL}{st['total']}{RESET}")
        print(f"  {DIM}Addresses  :{RESET} {st.get('addresses',0)}")
        print(f"  {DIM}First saved:{RESET} {st.get('first','?')}")
        print(f"  {DIM}Last saved :{RESET} {st.get('last','?')}")
        section("Vault Actions")
        print(f"  {BYEL}1{RESET}  Browse all records")
        print(f"  {BYEL}2{RESET}  Search by address")
        print(f"  {BYEL}3{RESET}  Search by keyword  (mnemonic word / note / combo)")
        print(f"  {BYEL}4{RESET}  Delete a record")
        print(f"  {BYEL}5{RESET}  Export to CSV")
        print(f"  {BYEL}6{RESET}  Export to TXT")
        print(f"  {BYEL}7{RESET}  Add / edit note on a record")
        print(f"  {BYEL}B{RESET}  Back to main menu")
        ch = prompt("Choice","B").strip().upper()
        if   ch == "B": return
        elif ch == "1": vault_browse_all(records)
        elif ch == "2": vault_search_addr(records)
        elif ch == "3": vault_search_keyword(records)
        elif ch == "4": vault_delete(records)
        elif ch == "5": vault_export_csv(records)
        elif ch == "6": vault_export_txt(records)
        elif ch == "7": vault_add_note(records)

def vault_browse_all(records):
    clr(); hdr("ALL VAULT RECORDS")
    PAGE=5; page=0; total=len(records)
    while True:
        start=page*PAGE; end=min(start+PAGE,total)
        for i,r in enumerate(records[start:end],start=start):
            print_record(r,i)
        print(f"\n  {DIM}Page {page+1}/{(total+PAGE-1)//PAGE}  Records {start+1}–{end}/{total}{RESET}")
        print(f"  {BYEL}N{RESET}ext  {BYEL}P{RESET}rev  {BYEL}B{RESET}ack")
        ch = prompt("","B").strip().upper()
        if ch == "B": return
        elif ch == "N":
            if end < total: page += 1
            else: warn("Already on last page.")
        elif ch == "P":
            if page > 0: page -= 1
            else: warn("Already on first page.")

def vault_search_addr(records):
    clr(); hdr("SEARCH BY ADDRESS")
    query = prompt("Enter address (full or partial)").strip()
    if not query: return
    hits = [(i,r) for i,r in enumerate(records)
            if any(query.lower() in a["address"].lower() for a in r.get("addresses",[]))]
    if not hits: warn("No records contain that address.")
    else:
        ok(f"Found {len(hits)} record(s):")
        for i,r in hits: print_record(r,i)
    press_enter()

def vault_search_keyword(records):
    clr(); hdr("SEARCH BY KEYWORD")
    query = prompt("Keyword (mnemonic word, note text, combo number)").strip().lower()
    if not query: return
    hits = []
    for i,r in enumerate(records):
        mn    = r.get("mnemonic","").lower()
        note  = r.get("note","").lower()
        combo = str(r.get("combo","")).lower()
        if query in mn or query in note or query in combo:
            hits.append((i,r))
    if not hits: warn("No matches.")
    else:
        ok(f"Found {len(hits)} record(s):")
        for i,r in hits: print_record(r,i)
    press_enter()

def vault_delete(records):
    clr(); hdr("DELETE A RECORD")
    for i,r in enumerate(records):
        ts=r.get("timestamp","?"); cmb=r.get("combo",[])
        print(f"  {BYEL}#{i+1}{RESET}  {ts}  combo={cmb}")
    raw = prompt("Record # to delete (blank=cancel)","")
    if not raw: return
    try:
        idx = int(raw)-1
        if 0 <= idx < len(records):
            r = records[idx]
            if yn(f"Delete record #{idx+1} ({r.get('timestamp')})?","n"):
                records.pop(idx); vault_save(records); ok("Deleted.")
        else: err("Out of range")
    except ValueError: err("Invalid number")
    press_enter()

def vault_export_csv(records):
    path = os.path.join(os.path.dirname(VAULT_FILE),"vault_export.csv")
    with open(path,'w',newline='',encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["timestamp","combo","mnemonic","type","path","address","note"])
        for r in records:
            ts=r.get("timestamp",""); mn=r.get("mnemonic","")
            cmb=str(r.get("combo",[])); note=r.get("note","")
            addrs=r.get("addresses",[])
            if addrs:
                for a in addrs:
                    w.writerow([ts,cmb,mn,a["type"],a["path"],a["address"],note])
            else:
                w.writerow([ts,cmb,mn,"","","",note])
    ok(f"CSV exported → {path}"); press_enter()

def vault_export_txt(records):
    path = os.path.join(os.path.dirname(VAULT_FILE),"vault_export.txt")
    with open(path,'w',encoding='utf-8') as f:
        f.write("BIP39 WALLET VAULT EXPORT\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("="*72+"\n")
        for i,r in enumerate(records):
            f.write(f"\nRecord #{i+1}\n")
            f.write(f"  Timestamp : {r.get('timestamp','')}\n")
            f.write(f"  Combo     : {r.get('combo',[])}\n")
            f.write(f"  Note      : {r.get('note','')}\n")
            f.write(f"  Mnemonic  : {r.get('mnemonic','')}\n")
            sh=r.get('seed_hex','')
            f.write(f"  Seed      : {sh[:64]}\n")
            f.write(f"             {sh[64:]}\n")
            for a in r.get("addresses",[]):
                f.write(f"  {a['type']}  {a['path']:<26}  {a['address']}\n")
            f.write("─"*72+"\n")
    ok(f"TXT exported → {path}"); press_enter()

def vault_add_note(records):
    clr(); hdr("ADD / EDIT NOTE")
    for i,r in enumerate(records):
        note=r.get("note",""); ts=r.get("timestamp","?"); cmb=r.get("combo",[])
        print(f"  {BYEL}#{i+1}{RESET}  {ts}  combo={cmb}  note={DIM}{note}{RESET}")
    raw = prompt("Record # to edit (blank=cancel)","")
    if not raw: return
    try:
        idx = int(raw)-1
        if 0 <= idx < len(records):
            new_note = prompt("New note", records[idx].get("note",""))
            records[idx]["note"] = new_note
            vault_save(records); ok("Note updated.")
        else: err("Out of range")
    except ValueError: err("Invalid")
    press_enter()

# ══════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════
def main_menu():
    if not run_tests(silent=True):
        clr()
        err("CRYPTO SELF-TEST FAILED — Aborting for safety.")
        err("Run option [T] for details.")
        press_enter(); sys.exit(1)

    while True:
        clr()
        bar("═",W,CYAN)
        print(CYAN+"║"+RESET+BG_BLU+BOLD+
              "   BIP39 / BIP32 / BIP44 / BIP49 / BIP84   WALLET TOOLKIT   ".center(W-2)+
              RESET+CYAN+"║"+RESET)
        bar("═",W,CYAN)

        st       = vault_stats()
        vinfo    = (f"{BGRN}● Vault:{RESET} {st['total']} records"
                    if st["total"]>0 else f"{DIM}○ Vault: empty{RESET}")
        accel    = (f"{BGRN}● coincurve: active{RESET}"
                    if USE_COINCURVE else f"{DIM}○ coincurve: not installed{RESET}")
        db_info  = addr_db_status()
        print(f"  {vinfo}   {accel}")
        print(f"  {db_info}")
        bar("─",W,DIM)

        print(f"\n  {BYEL}1{RESET}  Combo Generator      {DIM}SHA256(combo)→mnemonic→addresses{RESET}")
        print(f"  {BYEL}3{RESET}  Mnemonic Verify       {DIM}validate + derive all 3 address types{RESET}")
        print(f"  {BYEL}S{RESET}  Hunt Mode             {DIM}scan combos vs bruteaddress.txt  [% progress]{RESET}")
        print(f"  {BYEL}M{RESET}  Mnemonic Hunt         {DIM}scan mnemonic patterns  [% progress + checkpoint + ETA]{RESET}")
        print(f"  {BYEL}R{RESET}  Reload Address File   {DIM}re-read bruteaddress.txt from disk{RESET}")
        print(f"  {BYEL}U{RESET}  Mnemonic Hunt R       {DIM}permutation scanner  [% progress + checkpoint + ETA]{RESET}")
        print(f"  {BYEL}V{RESET}  Vault Browser         {DIM}search / export / manage saved results{RESET}")
        print(f"  {BYEL}T{RESET}  Run Self-Tests        {DIM}verify crypto against official BIP vectors{RESET}")
        print(f"  {BYEL}Q{RESET}  Quit\n")
        print(f"  {DIM}Tip: type  H  at any prompt to jump back here instantly{RESET}")
        print(f"  {DIM}Tip: create  hunt_pause.flag  to pause any running hunt{RESET}")
        print(f"  {DIM}Tip: matches + sessions logged to  hunt_log.txt{RESET}\n")
        print(f"  {DIM}Donate: bc1q5x9mwd352apqlqp23xdlulsndz9ceqgrjaw7aa   Buy me coffee only if this helped to find your forgotten wallet  Your support keeps THE JUMPERS free for everyone     Note: next updated version release:HORIZON 01 AUG 2026{RESET}")

        bar("─",W,DIM)

        try:
            ch = prompt("Select","1").strip().upper()
        except _HomeSignal:
            continue   # already at the home menu — just redraw it

        if   ch == "1":
            try:
                cfg = mode1_setup()
                if cfg: run_mode1(cfg)
            except _HomeSignal: pass
        elif ch == "3":
            try: run_mode3()
            except _HomeSignal: pass
        elif ch == "S":
            try: run_hunt()
            except _HomeSignal: pass
        elif ch == "M":
            try: run_mnemonic_hunt()
            except _HomeSignal: pass
        elif ch == "R":
            try:
                clr(); hdr("RELOAD ADDRESS FILE")
                _ADDR_DB.loaded = False
                if ensure_addr_db_loaded(force_reload=True):
                    ok("Address database reloaded.")
                press_enter()
            except _HomeSignal: pass
        elif ch == "U":
            try: run_mnemonic_hunt_permutation()
            except _HomeSignal: pass
        elif ch == "V":
            try: vault_browser()
            except _HomeSignal: pass
        elif ch == "T":
            try: clr(); run_tests(silent=False); press_enter()
            except _HomeSignal: pass
        elif ch == "Q":
            clr(); print(f"\n  {CYAN}Goodbye.{RESET}\n"); sys.exit(0)

# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Exited.{RESET}\n"); sys.exit(0)
    except _HomeSignal:
        # Safety net: should never escape main_menu(), but never crash if it does
        print(f"\n\n  {DIM}Exited.{RESET}\n"); sys.exit(0)
