
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">K</span>
          <div>
            <h1>KAAVALAL</h1>
            <p>Kerala Disaster Management</p>
          </div>
        </div>

        <div className="header-status">
          <span className="status-dot"></span>
          Dashboard Overview
        </div>
      </header>

      <div className="dashboard-layout">
        <aside className="sidebar">
          <p className="sidebar-label">MAIN MENU</p>

          <button className="nav-item active">▦ Dashboard</button>
          <button className="nav-item">⌖ Districts</button>
          <button className="nav-item">⚠ Hazards</button>
          <button className="nav-item">☂ Weather & Rainfall</button>
          <button className="nav-item">♧ Resources</button>
          <button className="nav-item">⌂ Shelters</button>

          <div className="sidebar-note">
            <span>KERALA, INDIA</span>
            <p>Disaster intelligence and response planning.</p>
          </div>
        </aside>

        <main className="main-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">STATE OVERVIEW</p>
              <h2>Disaster Intelligence Dashboard</h2>
              <p className="subtitle">
                Monitor district conditions across Kerala.
              </p>
            </div>

            <div className="demo-badge">WEEK 1 · DEMO</div>
          </section>

          <section className="stats-grid">
            <article className="stat-card">
              <div className="stat-top">
                <span>Kerala Districts</span>
                <span className="stat-icon blue">⌖</span>
              </div>
              <strong>14</strong>
              <p>Districts monitored</p>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Weather Status</span>
                <span className="stat-icon cyan">☁</span>
              </div>
              <strong>—</strong>
              <p>Awaiting weather data</p>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Active Hazards</span>
                <span className="stat-icon orange">⚠</span>
              </div>
              <strong>—</strong>
              <p>Awaiting hazard data</p>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Overall Risk</span>
                <span className="stat-icon purple">◇</span>
              </div>
              <strong>—</strong>
              <p>Risk assessment pending</p>
            </article>
          </section>

          <section className="content-grid">
            <article className="panel map-panel">
              <div className="panel-heading">
                <div>
                  <h3>Kerala District Map</h3>
                  <p>Geographic overview of the state</p>
                </div>
                <span className="panel-tag">MAP VIEW</span>
              </div>

              <div className="map-placeholder">
                <div className="map-symbol">⌖</div>
                <h3>Kerala Map</h3>
                <p>
                  The interactive district map will appear here.
                </p>
                <span className="map-caption">
                  GIS INTEGRATION · IN PROGRESS
                </span>
              </div>
            </article>

            <article className="panel district-panel">
              <div className="panel-heading">
                <div>
                  <h3>District Overview</h3>
                  <p>District information and risk details</p>
                </div>
              </div>

              <div className="empty-state">
                <div className="empty-icon">⌖</div>
                <h4>Select a district</h4>
                <p>
                  Choose a district from the map to view its details.
                </p>
              </div>

              <div className="district-footer">
                <span>STATE</span>
                <strong>Kerala, India</strong>
              </div>
            </article>
          </section>

          <footer className="footer">
            <span>KAAVALAL · DISASTER INTELLIGENCE PLATFORM</span>
            <span>Academic Capstone Project</span>
          </footer>
        </main>
      </div>
    </div>
  )
}

export default App
