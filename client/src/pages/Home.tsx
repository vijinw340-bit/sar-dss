import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Compass,
  FileText,
  Map as MapIcon,
  Navigation,
  Plane,
  Radar,
  Shield,
  Target,
  Wind,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";

const FEATURES = [
  {
    icon: Radar,
    title: "Search Area Calculation",
    desc: "Aviation-grade formulas compute distance, wind correction, navigation uncertainty and pilot deviation into a precise search radius and area from the LKP.",
  },
  {
    icon: Target,
    title: "Probability Zoning",
    desc: "High, medium and low probability zones are computed from heading, wind, elapsed time, speed and terrain — visualized in red, orange and yellow heat bands.",
  },
  {
    icon: Navigation,
    title: "Smart Search Patterns",
    desc: "Expanding square, sector, parallel track, creeping line and track line patterns are generated automatically with IAMSAR-style recommendation logic.",
  },
  {
    icon: MapIcon,
    title: "Interactive GIS Map",
    desc: "Leaflet-powered map with street, satellite, terrain and dark layers, sector division, airport overlays, grid coordinates and live mission rendering.",
  },
  {
    icon: Wind,
    title: "Live Weather & Drift",
    desc: "Open-Meteo integration brings live wind, visibility and forecast data that feeds directly into drift modelling and weather-impact prediction.",
  },
  {
    icon: FileText,
    title: "Professional PDF Reports",
    desc: "One-click mission reports with search parameters, probability maps, patterns, weather, coverage and sector allocation — exportable and emailable.",
  },
];

const STEPS = [
  { n: "01", t: "Create Mission", d: "Enter the aircraft details and the Last Known Position telemetry." },
  { n: "02", t: "Calculate", d: "The engine computes search radius, area, probability zones and patterns." },
  { n: "03", t: "Visualize", d: "Everything is plotted on the live GIS map with sectors and heat zones." },
  { n: "04", t: "Deploy & Report", d: "Assign aircraft to sectors, generate PDF reports and email them." },
];

export function Home() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-blue-50 dark:from-navy-950 dark:via-navy-900 dark:to-navy-950">
      {/* Navbar */}
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
            <Plane className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-base font-bold leading-tight text-navy-900 dark:text-white">SAR-DSS</p>
            <p className="text-[11px] text-muted-foreground">Airports Authority of India</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <Button asChild>
              <Link to="/dashboard">
                Open Console <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          ) : (
            <Button asChild>
              <Link to="/login">
                Sign in <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-6 pb-16 pt-10 text-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-flex items-center gap-2 rounded-full border bg-white/70 px-4 py-1.5 text-xs font-semibold text-primary dark:bg-white/10">
            <Shield className="h-3.5 w-3.5" /> Developed for the Airports Authority of India
          </span>
          <h1 className="mx-auto mt-6 max-w-4xl text-4xl font-extrabold leading-tight tracking-tight text-navy-900 dark:text-white md:text-6xl">
            Search &amp; Rescue <span className="text-primary">Decision Support</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground md:text-lg">
            Calculate and plot the probable search area of a missing aircraft from its
            <strong className="text-foreground"> Last Known Position (LKP)</strong> — with search radius,
            probability zones, recommended patterns and sector allocation on a live GIS map.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Button asChild size="lg" className="h-12 px-8 text-base">
              <Link to={user ? "/missions/new" : "/login"}>
                Create a Search Mission <Radar className="ml-1 h-5 w-5" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-8 text-base">
              <Link to="/dashboard">
                <Compass className="mr-1 h-5 w-5" /> Explore Dashboard
              </Link>
            </Button>
          </div>
        </motion.div>

        {/* Animated aircraft */}
        <motion.div
          className="relative mx-auto mt-14 max-w-md"
          animate={{ x: [0, 40, 0], y: [0, -12, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        >
          <div className="relative mx-auto flex h-56 w-56 items-center justify-center">
            <div className="absolute inset-0 rounded-full border-2 border-primary/20" />
            <div className="absolute inset-6 rounded-full border border-primary/30" />
            <div className="absolute inset-12 rounded-full border border-primary/40" />
            <span className="absolute inset-0 animate-radar rounded-full bg-primary/10" />
            <Plane className="relative z-10 h-16 w-16 -rotate-12 text-primary" />
          </div>
        </motion.div>
      </section>

      {/* Stats strip */}
      <section className="mx-auto max-w-7xl px-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { k: "Radius", v: "Distance + wind + uncertainty + deviation" },
            { k: "Patterns", v: "5 IAMSAR-standard search patterns" },
            { k: "Zones", v: "High / Medium / Low probability" },
            { k: "Reports", v: "PDF, CSV & email-ready" },
          ].map((s, i) => (
            <motion.div
              key={s.k}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="glass rounded-2xl p-5 text-left"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-primary">{s.k}</p>
              <p className="mt-1.5 text-sm text-muted-foreground">{s.v}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-navy-900 dark:text-white">Operational Capabilities</h2>
          <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
            Every module is fully functional — no placeholders. Built for the speed and clarity SAR coordinators need.
          </p>
        </div>
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06 }}
              className="glass rounded-2xl p-6 transition-transform hover:-translate-y-1"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <f.icon className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-base font-semibold text-navy-900 dark:text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-7xl px-6 pb-20">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-navy-900 dark:text-white">How It Works</h2>
        </div>
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-4">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="relative rounded-2xl border bg-card p-6"
            >
              <span className="text-3xl font-black text-primary/20">{s.n}</span>
              <h3 className="mt-3 font-semibold text-navy-900 dark:text-white">{s.t}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{s.d}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA + contact */}
      <section className="border-t bg-white/60 py-16 dark:bg-white/5">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <h2 className="text-2xl font-bold text-navy-900 dark:text-white">About SAR</h2>
          <p className="mx-auto mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            In civil aviation search and rescue, every minute matters. The quicker a probable search area is computed
            from the last known position, the smaller the drift error and the higher the chance of locating survivors.
            SAR-DSS standardizes this process for AAI's SAR officers using internationally recognized IAMSAR planning
            principles, GIS visualization and automated reporting.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4 text-sm">
            <span className="rounded-full border px-4 py-1.5 text-muted-foreground">✉️ sar-dss@aai.gov.in</span>
            <span className="rounded-full border px-4 py-1.5 text-muted-foreground">📞 SAR Ops Control: +91-11-2463 2045</span>
            <span className="rounded-full border px-4 py-1.5 text-muted-foreground">📍 Rajiv Gandhi Bhavan, New Delhi</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-navy-900 py-8 text-center text-xs text-slate-400">
        <p>© {new Date().getFullYear()} SAR-DSS · Airports Authority of India · Search and Rescue Decision Support System</p>
        <p className="mt-1">For official operational use only.</p>
      </footer>
    </div>
  );
}
