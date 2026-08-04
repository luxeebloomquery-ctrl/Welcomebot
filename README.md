# Setup Instructions (Mobile / GitHub)

## File upload karne ka tarika
1. Is zip ko extract karo (koi bhi file manager app se — ZArchiver ya built-in).
2. GitHub pe naya repo banao.
3. GitHub ke mobile web editor (github.com, "Add file" -> "Upload files" ya "Create new file") se ek-ek karke sab files upload karo, isi folder structure ke sath:

```
main.py
config.py
database.py
requirements.txt
Procfile            <-- IMPORTANT: neeche dekho
env.example.txt
handlers/__init__.py
handlers/welcome.py
handlers/album.py
handlers/owner.py
handlers/templates.py
handlers/editor.py
handlers/goodbye.py
handlers/card.py
handlers/backup.py
handlers/ownermgmt.py
handlers/scheduler.py
handlers/health.py
handlers/builder.py
utils/__init__.py
utils/buttons.py
utils/placeholders.py
utils/admin.py
utils/progress.py
utils/linkdetect.py
utils/video.py
utils/card.py
utils/ownercheck.py
utils/scheduler.py
utils/health.py
nixpacks.toml
```

## Phase 2 mein naya kya add hua (Smart Media Album)
- `/setalbum` - Multi-media album collection start karo (max 9 photo/video mixed)
- `/done <caption>` - Album save karo (progress bar dikhega collection ke dauran)
- `/cancel` - Album collection cancel karo
- Naya member join karne par agar album set hai to Telegram media-group ki tarah bhejta hai (buttons alag message mein, kyunki Telegram albums pe inline button allow nahi karta)

## Phase 3 mein naya kya add hua (Owner Panel)
- `/owner` - Dashboard (total groups, recent groups, recent broadcasts)
- `/broadcast` - Kisi bhi message (text/photo/video/GIF/sticker/document) ko reply karke sab groups mein bhejo, live progress bar ke sath
- `/groups` - Sab registered groups ki list
- `/stats` - Total groups + total known members (live progress ke sath calculate hota hai)
- `/deleteall` - Current chat mein pichhle 48 ghante ke bot-broadcast messages delete karo
- Smart link detector - broadcast mein link ho to 🔗 warning dikhta hai
- Agar koi group bot ko remove/block kar de to wo automatically list se hat jaata hai
- **Sirf OWNER_ID wala user hi ye commands use kar sakta hai** (group admin nahi)

## Phase 4 mein naya kya add hua (Templates + Editors)
- `/savetemplate` `/templates` `/loadtemplate` `/deltemplate` - Multiple welcome templates save/load karo
- `/randomwelcome on|off` - Har naye join pe random template pick hoga
- `/listbuttons` `/removebutton` `/previewbuttons` - Button editor
- `/addmedia` `/removemedia` `/replacemedia` `/reordermedia` `/listmedia` - Existing album edit karo (add/remove/replace/reorder)
- `/autodelete <sec>` - Welcome message N second baad khud delete ho jayega
- `/welcomedelay <sec>` - Welcome message N second delay se bhejega

## Phase 5 mein naya kya add hua (FFmpeg Video Processing)
- Koi bhi video (album ya single welcome media) agar 20 second se lamba hai to **automatically FFmpeg se trim** ho jaata hai — `/setalbum` collection ke dauran, `/addmedia`, `/replacemedia`, aur `/setwelcome` sabme
- Progress bar dikhta hai: download → duration check → trim → upload
- Ek time pe sirf ek video process hoti hai (built-in queue, taaki server overload na ho)
- Temp files hamesha cleanup ho jaate hai, chahe error aaye ya na aaye
- **IMPORTANT:** Railway pe FFmpeg install karne ke liye `nixpacks.toml` file zaroori hai — wo zip mein hai, bas usko bhi upload karna mat bhoolna (root folder mein, `main.py` ke sath)

## Phase 6 mein naya kya add hua (Goodbye + Card + Backup + Multi-Owner)
- `/goodbye on|off` `/setgoodbye` - Rose-style goodbye message (member leave hone par), text/media/buttons sab support
- `/cleanservice on|off` - Telegram ke native "X joined"/"X left" service messages auto-delete
- `/togglecard on|off` - Welcome ko ek design image-card ki tarah bhejo (avatar circle + name + member count)
- `/theme <naam>` - Card ka color theme: blue, dark, sunset, forest, purple
- `/backup` `/restore` - Group ka welcome+goodbye+templates config JSON file mein save/restore (admin level)
- `/export` `/import` - **Owner-only**: saare groups ka poora backup ek file mein
- `/clonewelcome <chat_id>` - **Owner-only**: current group ki welcome settings kisi doosre group mein copy karo
- `/addowner` `/removeowner` `/owners` - **Multi-owner support**, sirf super-owner (.env wala OWNER_ID) naye owners add/remove kar sakta hai
- `/ownerlogs` - Owner actions ka history (broadcast, delete, import, clone, owner add/remove)

## Phase 7 mein naya kya add hua (FINAL — Scheduler, Health, Live Builder, Compression)
- `/builder` - Interactive button-wizard: taps se welcome ON/OFF, text edit, card toggle, preview — sab bina command yaad rakhe
- `/schedulebroadcast <UTC date-time>` - **Owner-only**: message reply karke future date/time pe auto-broadcast schedule karo. Bot restart hone pe bhi job safe rehti hai (database-backed)
- `/pendingbroadcasts` `/cancelbroadcast <id>` - Scheduled broadcasts manage karo
- `/scheduletemplate <naam> <start> <end>` - Ek template ko date-range mein automatically active/revert karo (jaise Diwali special welcome)
- `/templateschedules` - Kaunse templates kab active honge, list dekho
- `/health` - **Owner-only**: uptime, memory usage, DB size, Python/aiogram version, group count — sab ek jagah
- **Media Compression**: video agar 8MB se bada hai (chahe 20 sec se chhota ho) to automatically compress hota hai (resolution+bitrate kam karke), bina quality bahut kharab kiye

## ⚠️ NAYA: Scheduler background mein chalta hai
Bot start hote hi ek background loop (`scheduler_loop`) har 30 second mein check karta hai ki koi scheduled broadcast ya template schedule due to hai. Isko alag se start karne ki zaroorat nahi — `main.py` khud handle karta hai.

## ⚠️ NAYA: Pillow font ke liye system package
Welcome Card ke liye `fonts-dejavu-core` bhi `nixpacks.toml` mein add ho gaya hai — Railway pe automatically install ho jayega, kuch alag se karne ki zaroorat nahi.

## ⚠️ IMPORTANT: Procfile rename karna hai
Zip ke andar `Procfile` ka naam **"Procfile.txt"** rakha gaya hai (kyunki bina extension wali files phone Gallery/file manager mein kabhi kabhi hidden ho jaati hain).

Upload karne ke baad GitHub pe:
1. `Procfile.txt` file kholo GitHub par
2. Pencil (edit) icon dabao
3. Upar filename box mein `Procfile.txt` ko sirf `Procfile` kar do (extension hata do)
4. Commit changes

Same tarah `env.example.txt` ko agar Railway/host `.env` chahta hai to us naam se rename kar sakte ho — lekin zyadatar cases mein aapko ye file ki zaroorat nahi, kyunki BOT_TOKEN aur OWNER_ID Railway ke "Variables" tab mein directly daalne hain, file upload nahi karni.

## Railway pe deploy
1. Railway pe naya project -> GitHub repo se deploy karo
2. Variables tab mein add karo:
   - `BOT_TOKEN` = apna bot token (BotFather se)
   - `OWNER_ID` = apni Telegram numeric user ID (@userinfobot se)
3. Deploy hote hi bot start ho jayega (Procfile automatically "worker" process chalayega)
