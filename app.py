from flask import Flask, jsonify, Response
import os, json, time

app = Flask(__name__)

# ===============================
# Config
# ===============================
SD_MOUNT_PATH = "/media/ployn/E25A-A181"
# แก้ตรงนี้: ห้ามใส่ "/" นำหน้าไฟล์ ไม่งั้น os.path.join จะพัง
JSON_FILE_PATH = os.path.join(SD_MOUNT_PATH, "noise_samples.json")

# ตำแหน่งตั้งต้นของแผนที่ (กรุงเทพฯประมาณนี้)
DEFAULT_CENTER = {"lat": 13.7276, "lng": 100.7726, "zoom": 20}

# ===============================
# Helper functions
# ===============================
def is_sdcard_mounted():
    """ตรวจว่า SD card ยัง mount อยู่และไฟล์ข้อมูลยังอยู่จริง"""
    return os.path.ismount(SD_MOUNT_PATH) and os.path.exists(JSON_FILE_PATH)

def read_measurements():
    """อ่านไฟล์ JSON แล้วคืนลิสต์จุดวัด (list of dicts)
       คาดว่าแต่ละอันเป็น {"lat":..,"lng":..,"dbm":..}
    """
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# ===============================
# Routes
# ===============================

@app.route("/")
def index():
    # หน้าเว็บหลัก: ตอนนี้มี 2 tab (Map / Table)
    html = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <title>RF 2.4GHz - Heatmap</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />

  <!-- Leaflet CSS/JS -->
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>

  <!-- Leaflet.heat -->
  <script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>

  <style>
    html, body {{
      height: 100%;
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
      background: #000;
      color: #fff;
    }}

    /* --- Layout หลัก --- */
    body {{
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}

    /* bar ด้านบน */
    #topbar {{
      flex-shrink: 0;
      background: rgba(0,0,0,0.8);
      color: #fff;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 16px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.6);
      position: relative;
      z-index: 1500;
    }}

    /* ปุ่มแท็บ */
    .tab-btn {{
      font-size: 13px;
      line-height: 1;
      background: rgba(255,255,255,0.07);
      color: #fff;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      min-width: 64px;
      text-align: center;
      transition: 0.15s;
    }}
    .tab-btn.active {{
      background: #0ea5e9;
      border-color: #0ea5e9;
      color: #000;
      font-weight: 600;
      box-shadow: 0 2px 6px rgba(14,165,233,0.5);
    }}
    .tab-btn:hover {{
      filter: brightness(1.15);
    }}

    /* ปุ่ม reload */
    #reload-btn {{
      margin-left: auto;
      padding: 8px 12px;
      font-size: 13px;
      background: #007bff;
      color: #fff;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      transition: 0.2s;
    }}
    #reload-btn:hover {{
      background: #0056b3;
    }}

    /* ส่วนคอนเทนต์หลักด้านล่าง */
    #content-wrapper {{
      position: relative;
      flex: 1;
      overflow: hidden;
      background: #000;
    }}

    /* map view กับ table view เป็น "หน้า" ที่สลับกัน */
    #map-view,
    #table-view {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}

    /* map element */
    #map {{
      width: 100%;
      height: 100%;
      background: #000;
    }}

    /* bubble info ขวาบน */
    .info-bubble {{
      position: absolute;
      top: 72px; /* ขยับลงเพราะมี topbar */
      right: 16px;
      background: rgba(0,0,0,0.6);
      color: #fff;
      font-size: 12px;
      line-height: 1.5;
      padding: 10px 12px;
      border-radius: 8px;
      max-width: 220px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      z-index: 1000;
    }}
    .info-bubble b {{
      font-weight: 600;
    }}
    .info-bubble code {{
      font-family: monospace;
      font-size: 12px;
      background: rgba(255,255,255,0.12);
      padding: 0 4px;
      border-radius: 4px;
      color: #fff;
    }}

    /* legend ซ้ายล่าง */
    .legend {{
      position: absolute;
      bottom: 16px;
      left: 16px;
      background: rgba(255,255,255,0.9);
      padding: 12px 14px;
      border-radius: 10px;
      font-size: 13px;
      line-height: 1.4;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      min-width: 220px;
      max-width: 240px;
      z-index: 1000;
      color: #000;
    }}
    .legend-title {{
      font-weight: 600;
      font-size: 13px;
      margin-bottom: 4px;
      color: #000;
    }}
    .legend-desc {{
      font-size: 12px;
      color: #444;
      margin-bottom: 8px;
    }}
    .legend-bar {{
      position: relative;
      width: 100%;
      height: 12px;
      border-radius: 6px;
      background: linear-gradient(
        to right,
        #00f,
        #0ff,
        #0f0,
        #ff0,
        #f00
      );
      box-shadow: inset 0 0 3px rgba(0,0,0,0.4);
      margin-bottom: 4px;
    }}
    .legend-scale {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #000;
      font-family: monospace;
    }}
    .legend-label-row {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      margin-top: 6px;
      color: #555;
      font-weight: 500;
    }}
    .legend-footnote {{
      margin-top: 8px;
      font-size: 11px;
      color: #666;
    }}

    /* สถานะ SD card มุมล่างขวา */
    #sd-status {{
      position: absolute;
      right: 16px;
      bottom: 16px;
      background: rgba(0,0,0,0.6);
      color: #fff;
      font-size: 12px;
      padding: 8px 10px;
      border-radius: 8px;
      line-height: 1.4;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      min-width: 160px;
      text-align: left;
      z-index: 1000;
      font-family: system-ui, sans-serif;
    }}
    #sd-status .label {{
      font-size: 11px;
      color: #ccc;
    }}
    #sd-status .state {{
      font-weight: 600;
      font-size: 12px;
    }}
    #sd-status .time {{
      font-size: 10px;
      color: #aaa;
      margin-top: 4px;
      font-family: monospace;
      word-spacing: -2px;
    }}

    /* ======================= TABLE VIEW ======================= */
    #table-view {{
      background: #0a0a0a;
      display: flex;
      flex-direction: column;
      padding: 16px;
      box-sizing: border-box;
      color: #fff;
      font-size: 13px;
      line-height: 1.4;
    }}

    #table-header {{
      flex-shrink: 0;
      color: #fff;
      margin-bottom: 8px;
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      flex-wrap: wrap;
      row-gap: 6px;
    }}

    #table-header-left {{
      font-size: 14px;
      font-weight: 600;
      color: #fff;
    }}

    #table-meta {{
      font-size: 11px;
      color: #aaa;
      font-family: monospace;
    }}

    #table-scroll {{
      flex: 1;
      min-height: 0;
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 8px;
      background: rgba(255,255,255,0.03);
      box-shadow: 0 2px 8px rgba(0,0,0,0.8);
      overflow: auto;
    }}

    table.data-table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 360px;
      font-size: 12px;
      color: #eee;
    }}

    table.data-table thead {{
      position: sticky;
      top: 0;
      background: rgba(14,165,233,0.15);
      backdrop-filter: blur(4px);
      color: #0ea5e9;
      font-weight: 600;
      text-align: left;
      box-shadow: 0 2px 4px rgba(0,0,0,0.8);
      z-index: 10;
    }}

    table.data-table th,
    table.data-table td {{
      padding: 8px 10px;
      border-bottom: 1px solid rgba(255,255,255,0.07);
      white-space: nowrap;
      text-overflow: ellipsis;
      overflow: hidden;
      font-variant-numeric: tabular-nums;
    }}

    table.data-table tbody tr:hover {{
      background: rgba(255,255,255,0.07);
    }}

    .col-idx {{ color: #888; width: 3rem; }}
    .col-lat, .col-lng {{ color: #fff; }}
    .col-dbm {{ font-weight: 600; }}

    /* ซ่อน view ที่ไม่ได้ active */
    .hidden {{
      display: none !important;
    }}

  </style>
</head>
<body>

  <!-- top bar -->
  <div id="topbar">
    <button class="tab-btn active" id="tab-map">Map</button>
    <button class="tab-btn" id="tab-table">Table</button>

    <button id="reload-btn">🔄 Reload Data</button>
  </div>

  <!-- content wrapper -->
  <div id="content-wrapper">

    <!-- MAP VIEW -->
    <div id="map-view">
      <!-- bubble ขวาบน -->
      <div class="info-bubble">
        <b>Point format ตัวอย่าง</b><br/>
        <code>{{"lat": 13.7563, "lng": 100.5018, "dbm": -85}}</code><br/><br/>
        lat / lng = ตำแหน่งบนแผนที่<br/>
        dbm = ความเข้มสัญญาน
      </div>

      <!-- legend ซ้ายล่าง -->
      <div class="legend">
        <div class="legend-title">RF2.4GHzHeatmap</div>
        <div class="legend-desc">
          สีแดง = ความเข้มสัญญานสูง<br/>
          สีน้ำเงิน = ความเข้มสัญญานต่ำ
        </div>

        <div class="legend-bar"></div>

        <div class="legend-scale">
          <div>-60</div>
          <div>-50</div>
          <div>-40</div>
          <div>-30</div>
        </div>

        <div class="legend-label-row">
          <div>ความเข้มสัญญานต่ำ</div>
          <div>ความเข้มสัญญานสูง</div>
        </div>

        <div class="legend-footnote">
          หน่วย: dBm<br/>
        </div>
      </div>

      <!-- สถานะ SD card -->
      <div id="sd-status">
        <div class="label">SD card:</div>
        <div class="state" id="sd-state">กำลังตรวจสอบ...</div>
        <div class="time" id="sd-time">--:--:--</div>
      </div>

      <!-- ตัวแผนที่ -->
      <div id="map"></div>
    </div>

    <!-- TABLE VIEW -->
    <div id="table-view" class="hidden">
      <div id="table-header">
        <div id="table-header-left">ข้อมูลดิบทั้งหมด (Raw Samples)</div>
        <div id="table-meta">
          Rows: <span id="row-count">0</span> |
          Updated: <span id="table-time">--:--:--</span>
        </div>
      </div>

      <div id="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-idx">#</th>
              <th class="col-lat">lat</th>
              <th class="col-lng">lng</th>
              <th class="col-dbm">dBm</th>
            </tr>
          </thead>
          <tbody id="table-body">
            <!-- rows inject by JS -->
          </tbody>
        </table>
      </div>
    </div>

  </div> <!-- /content-wrapper -->

<script>
(async () => {{

  // ======== TAB SWITCHING ========
  const tabMapBtn = document.getElementById("tab-map");
  const tabTableBtn = document.getElementById("tab-table");
  const mapView = document.getElementById("map-view");
  const tableView = document.getElementById("table-view");

  function switchTo(tabName) {{
    if (tabName === "map") {{
      tabMapBtn.classList.add("active");
      tabTableBtn.classList.remove("active");
      mapView.classList.remove("hidden");
      tableView.classList.add("hidden");

      // Leaflet ต้อง invalidateSize หลัง show
      if (window._leafletMap) {{
        setTimeout(() => {{
          window._leafletMap.invalidateSize();
        }}, 200);
      }}
    }} else {{
      tabTableBtn.classList.add("active");
      tabMapBtn.classList.remove("active");
      tableView.classList.remove("hidden");
      mapView.classList.add("hidden");

      // โหลดข้อมูลตารางทุกครั้งที่กด Tab "Table"
      populateTable();
    }}
  }}

  tabMapBtn.addEventListener("click", () => switchTo("map"));
  tabTableBtn.addEventListener("click", () => switchTo("table"));

  // =============== Map setup ===============
  const map = L.map('map').setView(
    [{DEFAULT_CENTER["lat"]}, {DEFAULT_CENTER["lng"]}],
    {DEFAULT_CENTER["zoom"]}
  );
  window._leafletMap = map;

  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }}).addTo(map);

  // Heat layer object (เราจะเซ็ตทีหลังตอนโหลดข้อมูล)
  let heatLayer = null;
  let pointMarkers = [];

  // แปลง dBm -> intensity (0..1)
  // mapping ตาม legend: -110 (เย็น) → ต่ำ, -60 (ร้อน) → สูง
  function dbmToIntensity(dbm) {{
    const min = -60; // น้อย/อ่อน
    const max = -30;  // รุนแรง/แรง
    let x = (dbm - min) / (max - min); // normalize 0..1
    x = Math.max(0, Math.min(1, x));
    return 0.05 + x * 0.95; // boost นิดหน่อยให้มองเห็น
  }}

  // วาดข้อมูลลง heatmap + จุด popup
  function renderData(rawPoints) {{
    // เคลียร์ของเดิม
    if (heatLayer) {{
      map.removeLayer(heatLayer);
    }}
    pointMarkers.forEach(m => map.removeLayer(m));
    pointMarkers = [];

    if (!Array.isArray(rawPoints)) {{
      return;
    }}

    // เตรียมข้อมูล heatmap
    const heatArray = rawPoints.map(p => [p.lat, p.lng, dbmToIntensity(p.dbm)]);
    heatLayer = L.heatLayer(heatArray, {{
      radius: 28,
      blur: 18,
      maxZoom: 17
    }}).addTo(map);

    // จุดวัดจริงเล็ก ๆ + popup
    rawPoints.forEach(p => {{
      const marker = L.circleMarker([p.lat, p.lng], {{
        radius: 3,
        weight: 0,
        fillOpacity: 0.8
      }})
      .bindPopup(
        "<div style='font-size:11px; line-height:1.4;'>"
        + "<b>dBm:</b> " + p.dbm + "<br/>"
        + "<b>lat:</b> " + p.lat + "<br/>"
        + "<b>lng:</b> " + p.lng + "</div>"
      )
      .addTo(map);

      pointMarkers.push(marker);
    }});
  }}

  // โหลดข้อมูลจาก Flask สำหรับแผนที่
  async function fetchData() {{
    const res = await fetch('/data');
    const data = await res.json();
    if (data.error) {{
      console.warn("⚠ /data error:", data.error);
      // เคลียร์ heatmap ถ้ามี
      if (heatLayer) {{
        map.removeLayer(heatLayer);
        heatLayer = null;
      }}
      pointMarkers.forEach(m => map.removeLayer(m));
      pointMarkers = [];
      return [];
    }}
    renderData(data);
    return data;
  }}

  // โหลดข้อมูลแบบตาราง (สำหรับ tab Table)
  async function populateTable() {{
    const tbody = document.getElementById("table-body");
    const rowCountEl = document.getElementById("row-count");
    const tableTimeEl = document.getElementById("table-time");

    tbody.innerHTML = "<tr><td colspan='4' style='color:#999;padding:12px;'>Loading...</td></tr>";

    try {{
      const res = await fetch('/tabledata');
      const rows = await res.json();

      if (rows.error) {{
        tbody.innerHTML = "<tr><td colspan='4' style='color:#f87171;padding:12px;'>"
                        + "Error: " + rows.error + "</td></tr>";
        rowCountEl.textContent = "0";
        tableTimeEl.textContent = "--:--:--";
        return;
      }}

      // เติมตารางใหม่
      tbody.innerHTML = "";
      rows.forEach(r => {{
        const tr = document.createElement("tr");

        const tdIdx = document.createElement("td");
        tdIdx.className = "col-idx";
        tdIdx.textContent = r.idx;
        tr.appendChild(tdIdx);

        const tdLat = document.createElement("td");
        tdLat.className = "col-lat";
        tdLat.textContent = r.lat;
        tr.appendChild(tdLat);

        const tdLng = document.createElement("td");
        tdLng.className = "col-lng";
        tdLng.textContent = r.lng;
        tr.appendChild(tdLng);

        const tdDbm = document.createElement("td");
        tdDbm.className = "col-dbm";
        tdDbm.textContent = r.dbm;
        tr.appendChild(tdDbm);

        tbody.appendChild(tr);
      }});

      // อัปเดต meta
      rowCountEl.textContent = rows.length;
      const now = new Date();
      const hh = String(now.getHours()).padStart(2,"0");
      const mm = String(now.getMinutes()).padStart(2,"0");
      const ss = String(now.getSeconds()).padStart(2,"0");
      tableTimeEl.textContent = hh+":"+mm+":"+ss;

    }} catch(e) {{
      tbody.innerHTML = "<tr><td colspan='4' style='color:#facc15;padding:12px;'>"
                      + "⚠ Failed to load table: "+e+"</td></tr>";
      rowCountEl.textContent = "0";
      tableTimeEl.textContent = "--:--:--";
    }}
  }}

  // อัปเดตสถานะ SD card
  async function updateSDStatus() {{
    const stateEl = document.getElementById("sd-state");
    const timeEl = document.getElementById("sd-time");

    try {{
      const res = await fetch('/sdstatus');
      const info = await res.json();

      const now = new Date();
      const hh = String(now.getHours()).padStart(2,"0");
      const mm = String(now.getMinutes()).padStart(2,"0");
      const ss = String(now.getSeconds()).padStart(2,"0");
      timeEl.textContent = hh+":"+mm+":"+ss;

      if (info.mounted) {{
        stateEl.textContent = "ONLINE ✓  (" + info.points + " points)";
        stateEl.style.color = "#4ade80"; // เขียว
      }} else {{
        stateEl.textContent = "OFFLINE ✗  (no card)";
        stateEl.style.color = "#f87171"; // แดง
      }}
    }} catch (e) {{
      stateEl.textContent = "UNKNOWN ?";
      stateEl.style.color = "#facc15"; // เหลือง
      timeEl.textContent = "--:--:--";
    }}
  }}

  // ปุ่ม Reload → เรียก /reload แล้วรีเฟรชข้อมูล map/table/status
  const reloadButton = document.getElementById("reload-btn");
  reloadButton.addEventListener("click", async () => {{
    reloadButton.textContent = "⏳ Reloading...";
    try {{
      const res = await fetch('/reload');
      const info = await res.json();

      if (info.status === "ok") {{
        alert(`✅ Reload success — ${{info.count}} points loaded!`);
        await fetchData();
        await updateSDStatus();

        // ถ้าเราอยู่หน้า Table อยู่ ให้รีเฟรชตารางด้วย
        if (tabTableBtn.classList.contains("active")) {{
          await populateTable();
        }}
      }} else {{
        alert("⚠ " + (info.error || "Unknown error"));
      }}
    }} catch (e) {{
      alert("❌ Reload failed: " + e);
    }} finally {{
      reloadButton.textContent = "🔄 Reload Data";
    }}
  }});

  // --- เรียกครั้งแรกตอนโหลดหน้า ---
  await fetchData();
  await updateSDStatus();

  // อัปเดตสถานะ SD card ทุก ๆ 5 วินาที
  setInterval(updateSDStatus, 5000);

}})();
</script>

</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.route("/data")
def data():
    """
    คืนข้อมูลจุดวัดสำหรับ heatmap
    ถ้า SD card ไม่เจอ -> ส่ง error
    """
    if not is_sdcard_mounted():
        return jsonify({
            "error": "SD card not detected or file not found.",
            "hint": SD_MOUNT_PATH
        }), 404

    try:
        pts = read_measurements()
        return jsonify(pts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/tabledata")
def tabledata():
    """
    ส่งข้อมูลเป็น list ของจุดวัดทั้งหมด เอาไว้ populate ตาราง
    เราจะใส่ index ให้ดูง่าย (#)
    รูปแบบ:
    [
      {"idx":0, "lat":..., "lng":..., "dbm":...},
      {"idx":1, ...},
      ...
    ]
    """
    if not is_sdcard_mounted():
        return jsonify({
            "error": "SD card not detected or file not found.",
            "hint": SD_MOUNT_PATH
        }), 404

    try:
        pts = read_measurements()
        table_rows = []
        for i, p in enumerate(pts):
            table_rows.append({
                "idx": i,
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "dbm": p.get("dbm")
            })
        return jsonify(table_rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reload")
def reload_data():
    """
    สำหรับปุ่ม Reload Data:
    - เช็กว่ามี SD card ไหม
    - อ่านไฟล์อีกรอบเพื่อ confirm ว่าอ่านได้
    - คืนจำนวนจุดเพื่อโชว์แจ้งเตือน
    """
    if not is_sdcard_mounted():
        return jsonify({"error": "SD card not detected."}), 404

    try:
        pts = read_measurements()
        return jsonify({"status": "ok", "count": len(pts)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/sdstatus")
def sd_status():
    """
    สำหรับแสดงสถานะมุมขวาล่างแบบ real-time
    คืน:
    - mounted: True/False
    - points: นับจำนวนจุดในไฟล์ (ถ้าอ่านได้)
    """
    mounted = is_sdcard_mounted()
    info = {
        "mounted": mounted,
        "mount_path": SD_MOUNT_PATH,
        "timestamp": time.time()
    }

    if mounted:
        try:
            pts = read_measurements()
            info["points"] = len(pts)
        except Exception:
            info["points"] = 0
    else:
        info["points"] = 0

    return jsonify(info)


# ===============================
# main
# ===============================
if __name__ == "__main__":
    # รัน Flask ให้เข้าถึงจากเครื่องอื่นใน LAN ได้
    app.run(host="0.0.0.0", port=5000, debug=True)
