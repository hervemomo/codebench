import React, { useState, useRef, useCallback } from "react";
import {
  Plus, ChevronDown, ChevronRight, FileText, Upload as UploadIcon,
  Settings, User, ArrowLeft, ArrowRight, Edit2, Trash2, Sliders,
  Languages, Check, Sparkles, BookOpen, Scissors, GitMerge,
  BarChart3, Grid3x3, Search, Download, Folder, X, ThumbsUp, ThumbsDown,
  Layers, ArrowRightLeft, RotateCcw, Table2, Image,
  CheckCircle2, XCircle, Eye, ChevronUp, EyeOff, AlertCircle, Link2, ZapIcon,
  ShieldCheck, Copy, HelpCircle, MessageSquareWarning, Pin, PinOff,
  AlertTriangle, MoreVertical, Archive, ArchiveRestore
} from "lucide-react";

/* ---------------------------------------------------------
   DESIGN TOKENS
   Subject: a qualitative-coding workbench for market research
   analysts — people moving hundreds of open-ended survey
   answers through cleaning → AI coding → human refinement.
   The signature idea: a persistent "thread" rail on the left
   showing exactly where you are in the per-question pipeline,
   because that orientation problem is the real content of
   this brief (not the visual decoration).
--------------------------------------------------------- */

const T = {
  primary: "#3A5FFF",
  primarySoft: "#EEF1FF",
  bg: "#F5F7FA",
  surface: "#FFFFFF",
  border: "#E5E7EB",
  text: "#1F2937",
  textMuted: "#6B7280",
  accent: "#10B981",
};

const STAGES = ["Upload", "Preprocess", "Code", "QA Review", "Refinement", "Results"];
const STAGE_ICONS = [UploadIcon, Sliders, Sparkles, ShieldCheck, GitMerge, BarChart3];
const STAGE_PAGES = ["upload", "preprocess", "code", "qa", "refinement", "results"];

const PAGES = [
  "projects", "create-project", "context", "add-question",
  "upload", "preprocess", "code", "refinement", "results"
];

/* ---------- shared chrome ---------- */

function TopBar({ page }) {
  const titles = {
    projects: "Projects",
    "create-project": "Create New Project",
    context: "Project — SABC-MAY2026",
    "add-question": "Add Question",
    upload: "Upload Responses",
    preprocess: "Preprocess Responses",
    code: "Coding — Generate & Apply Codebook",
    qa: "QA Review — Before You Trust the Results",
    refinement: "Refinement",
    results: "Results — Explore Insights & Exports",
  };
  return (
    <div style={{
      height: 64, display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 28px", borderBottom: `1px solid ${T.border}`, background: T.surface,
      flexShrink: 0,
    }}>
      <h1 style={{ fontSize: 19, fontWeight: 600, color: T.text, margin: 0, letterSpacing: "-0.01em" }}>
        {titles[page]}
      </h1>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ fontSize: 13, color: T.textMuted }}>SABC Research Co.</span>
        <div style={{
          width: 32, height: 32, borderRadius: "50%", background: T.primarySoft,
          display: "flex", alignItems: "center", justifyContent: "center", color: T.primary,
        }}>
          <User size={16} />
        </div>
      </div>
    </div>
  );
}

function Sidebar({ page, go }) {
  const [projectOpen, setProjectOpen] = useState(true);
  const [questionsOpen, setQuestionsOpen] = useState(true);
  const [pinned, setPinned] = useState(true);
  const [hovered, setHovered] = useState(false);
  const stageIndex = STAGE_PAGES.indexOf(page);
  const inPipeline = stageIndex !== -1;

  const expanded = pinned || hovered; // whether full-width content is shown
  const COLLAPSED_W = 64;
  const EXPANDED_W = 248;

  const navItem = (label, target, Icon, active) => (
    <button
      key={label}
      onClick={() => go(target)}
      style={{
        display: "flex", alignItems: "center", gap: 9, width: "100%",
        padding: "7px 10px", borderRadius: 7, border: "none", cursor: "pointer",
        background: active ? T.primarySoft : "transparent",
        color: active ? T.primary : T.textMuted,
        fontSize: 13.5, fontWeight: active ? 600 : 500, textAlign: "left",
      }}
    >
      {Icon && <Icon size={14} />}
      {label}
    </button>
  );

  // Compact icon-only button used when the rail is collapsed
  const railIcon = (Icon, target, active, key, title) => (
    <button
      key={key}
      onClick={() => go(target)}
      title={title}
      style={{
        width: 34, height: 34, borderRadius: 8, border: "none", cursor: "pointer",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: active ? T.primarySoft : "transparent",
        color: active ? T.primary : T.textMuted,
        margin: "0 auto 4px",
      }}
    >
      <Icon size={16} />
    </button>
  );

  return (
    <div style={{ width: pinned ? EXPANDED_W : COLLAPSED_W, flexShrink: 0, height: "100%", position: "relative" }}>
    <div
      onMouseEnter={() => !pinned && setHovered(true)}
      onMouseLeave={() => !pinned && setHovered(false)}
      style={{
        width: expanded ? EXPANDED_W : COLLAPSED_W,
        position: pinned ? "relative" : "absolute",
        top: 0, left: 0, background: T.surface,
        borderRight: `1px solid ${T.border}`, display: "flex", flexDirection: "column",
        height: "100%", overflow: "hidden", transition: "width 0.16s ease, box-shadow 0.16s ease",
        boxShadow: !pinned && hovered ? "6px 0 20px rgba(15,23,42,0.14)" : "none",
        zIndex: 30,
      }}
    >
      {expanded ? (
        <>
          <div style={{ padding: "18px 16px 8px" }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 8, marginBottom: 18,
              fontSize: 15, fontWeight: 700, color: T.text,
            }}>
              <div style={{
                width: 26, height: 26, borderRadius: 7, background: T.primary,
                display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0,
              }}><Sparkles size={14} /></div>
              <span style={{ flex: 1, whiteSpace: "nowrap" }}>Codebench</span>
              <button
                onClick={() => setPinned(p => !p)}
                title={pinned ? "Unpin sidebar" : "Pin sidebar open"}
                style={{
                  width: 26, height: 26, borderRadius: 7, border: `1px solid ${T.border}`,
                  background: pinned ? T.primarySoft : T.surface, color: pinned ? T.primary : T.textMuted,
                  cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}
              >
                {pinned ? <Pin size={13} /> : <PinOff size={13} />}
              </button>
            </div>

            <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.06em", marginBottom: 6, paddingLeft: 2 }}>
              PROJECTS
            </div>
            <button onClick={() => go("create-project")} style={{
              display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "7px 10px",
              borderRadius: 7, border: "none", background: "transparent", color: T.primary,
              fontSize: 13.5, fontWeight: 600, cursor: "pointer", marginBottom: 4,
            }}>
              <Plus size={14} /> Create Project
            </button>

            <button onClick={() => setProjectOpen(o => !o)} style={{
              display: "flex", alignItems: "center", gap: 6, width: "100%", padding: "7px 10px",
              border: "none", background: "transparent", cursor: "pointer", fontSize: 13.5,
              fontWeight: 600, color: T.text,
            }}>
              {projectOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Folder size={13} style={{ color: T.textMuted }} /> SABC-MAY2026
            </button>

            {projectOpen && (
              <div style={{ marginLeft: 20, borderLeft: `1px solid ${T.border}`, paddingLeft: 10 }}>
                {navItem("Context", "context", FileText, page === "context")}
                <button onClick={() => setQuestionsOpen(o => !o)} style={{
                  display: "flex", alignItems: "center", gap: 6, width: "100%", padding: "7px 10px",
                  border: "none", background: "transparent", cursor: "pointer", fontSize: 13,
                  fontWeight: 600, color: T.textMuted,
                }}>
                  {questionsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />} Questions
                </button>
                {questionsOpen && (
                  <div style={{ marginLeft: 14 }}>
                    <button onClick={() => go("upload")} style={{
                      display: "block", width: "100%", textAlign: "left", padding: "6px 10px",
                      fontSize: 12.5, border: "none", borderRadius: 6, cursor: "pointer",
                      background: inPipeline ? T.primarySoft : "transparent",
                      color: inPipeline ? T.primary : T.textMuted, fontWeight: inPipeline ? 600 : 500,
                    }}>
                      Pourquoi aimez-vous cette boisson&nbsp;?
                    </button>
                    <button style={{
                      display: "block", width: "100%", textAlign: "left", padding: "6px 10px",
                      fontSize: 12.5, border: "none", borderRadius: 6, cursor: "pointer",
                      background: "transparent", color: T.textMuted,
                    }}>
                      Qu'est-ce qui vous fait acheter…
                    </button>
                  </div>
                )}
                <button onClick={() => go("add-question")} style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", marginTop: 2,
                  border: "none", background: "transparent", color: T.primary, fontSize: 12.5,
                  fontWeight: 600, cursor: "pointer",
                }}>
                  <Plus size={12} /> Add question
                </button>
              </div>
            )}
          </div>

          {inPipeline && (
            <div style={{ padding: "14px 16px", borderTop: `1px solid ${T.border}`, marginTop: 4 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.06em", marginBottom: 10, paddingLeft: 2 }}>
                WORKFLOW
              </div>
              <div style={{ position: "relative", paddingLeft: 6 }}>
                {STAGES.map((s, i) => {
                  const Icon = STAGE_ICONS[i];
                  const active = i === stageIndex;
                  const done = i < stageIndex;
                  return (
                    <button key={s} onClick={() => go(STAGE_PAGES[i])} style={{
                      display: "flex", alignItems: "center", gap: 10, width: "100%",
                      padding: "8px 8px", border: "none", background: "transparent",
                      cursor: "pointer", position: "relative",
                    }}>
                      <div style={{
                        width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        background: active ? T.primary : done ? T.accent : T.bg,
                        border: active || done ? "none" : `1.5px solid ${T.border}`,
                        color: active || done ? "#fff" : T.textMuted,
                      }}>
                        {done ? <Check size={12} /> : <Icon size={11} />}
                      </div>
                      <span style={{
                        fontSize: 13, fontWeight: active ? 700 : 500,
                        color: active ? T.text : T.textMuted, whiteSpace: "nowrap",
                      }}>{s}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ marginTop: "auto", padding: "14px 16px", borderTop: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.06em", marginBottom: 6, paddingLeft: 2 }}>
              ADMIN
            </div>
            {navItem("System Setup", "admin", Settings, false)}
            {navItem("Model Defaults", "admin", Settings, false)}
            <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.06em", margin: "10px 0 6px", paddingLeft: 2 }}>
              SETTINGS
            </div>
            {navItem("User Profile", "settings", User, false)}
          </div>
        </>
      ) : (
        /* ── Collapsed icon-only rail ── */
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", height: "100%", padding: "18px 0 14px" }}>
          <div style={{
            width: 26, height: 26, borderRadius: 7, background: T.primary,
            display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", marginBottom: 10,
          }}><Sparkles size={14} /></div>

          <button
            onClick={() => setPinned(true)}
            title="Pin sidebar open"
            style={{
              width: 26, height: 26, borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface,
              color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              marginBottom: 18,
            }}
          >
            <PinOff size={12} />
          </button>

          {railIcon(Folder, "context", page === "context" || inPipeline, "proj", "SABC-MAY2026")}
          {railIcon(Plus, "add-question", false, "addq", "Add question")}

          {inPipeline && (
            <>
              <div style={{ width: 24, height: 1, background: T.border, margin: "10px 0" }} />
              {STAGES.map((s, i) => {
                const Icon = STAGE_ICONS[i];
                const active = i === stageIndex;
                const done = i < stageIndex;
                return (
                  <button key={s} onClick={() => go(STAGE_PAGES[i])} title={s} style={{
                    width: 34, height: 34, borderRadius: "50%", border: active || done ? "none" : `1.5px solid ${T.border}`,
                    cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                    background: active ? T.primary : done ? T.accent : T.surface,
                    color: active || done ? "#fff" : T.textMuted,
                    margin: "0 auto 8px", flexShrink: 0,
                  }}>
                    {done ? <Check size={13} /> : <Icon size={13} />}
                  </button>
                );
              })}
            </>
          )}

          <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div style={{ width: 24, height: 1, background: T.border, margin: "10px 0" }} />
            {railIcon(Settings, "admin", false, "admin", "Admin")}
            {railIcon(User, "settings", false, "settings", "Settings")}
          </div>
        </div>
      )}
    </div>
    </div>
  );
}

/* ---------- small ui atoms ---------- */

function Card({ children, style }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10,
      padding: 22, boxShadow: "0 1px 2px rgba(16,24,40,0.04)", ...style,
    }}>{children}</div>
  );
}

/* Type-to-confirm deletion modal. Requires the exact project name before
   the destructive action can be taken — the standard pattern for
   irreversible, high-consequence deletes. */
function DeleteProjectModal({ project, onCancel, onConfirm }) {
  const [confirmText, setConfirmText] = useState("");
  const canDelete = confirmText === project.name;

  return (
    <div
      onClick={onCancel}
      style={{
        position: "fixed", inset: 0, background: "rgba(15,23,42,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 200, padding: 20,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: T.surface, borderRadius: 14, width: "100%", maxWidth: 440,
          boxShadow: "0 20px 50px rgba(15,23,42,0.25)", overflow: "hidden",
        }}
      >
        <div style={{ padding: "22px 24px 0" }}>
          <div style={{
            width: 42, height: 42, borderRadius: 11, background: "#FEF2F2",
            display: "flex", alignItems: "center", justifyContent: "center", color: "#EF4444", marginBottom: 14,
          }}>
            <AlertTriangle size={20} />
          </div>
          <h3 style={{ margin: "0 0 6px", fontSize: 16.5, fontWeight: 700, color: T.text }}>
            Delete "{project.name}"?
          </h3>
          <p style={{ margin: "0 0 14px", fontSize: 13.5, color: T.textMuted, lineHeight: 1.55 }}>
            This action <strong style={{ color: T.text }}>cannot be undone</strong>. Deleting this project will permanently remove:
          </p>
          <ul style={{ margin: "0 0 16px", padding: "0 0 0 18px", fontSize: 13, color: T.textMuted, lineHeight: 1.9 }}>
            <li>All {project.questionCount} question{project.questionCount !== 1 ? "s" : ""} and their coding pipelines</li>
            <li>Uploaded responses, preprocessing settings, and codebooks</li>
            <li>Coded data, refinement history, and results</li>
            <li>Any generated exports linked to this project</li>
          </ul>
          <div style={{
            display: "flex", gap: 8, alignItems: "flex-start", padding: "10px 12px",
            borderRadius: 8, background: "#FEF2F2", border: "1px solid #FECACA", marginBottom: 18,
          }}>
            <AlertCircle size={14} style={{ color: "#EF4444", flexShrink: 0, marginTop: 1 }} />
            <span style={{ fontSize: 12.5, color: "#991B1B", lineHeight: 1.5 }}>
              This is permanent. The data will be gone forever — there is no recovery, trash, or archive.
            </span>
          </div>

          <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: T.textMuted, marginBottom: 6 }}>
            Type <strong style={{ color: T.text }}>{project.name}</strong> to confirm
          </label>
          <input
            autoFocus
            value={confirmText}
            onChange={e => setConfirmText(e.target.value)}
            placeholder={project.name}
            style={{
              ...inputStyle, marginBottom: 20,
              borderColor: confirmText.length > 0 ? (canDelete ? T.accent : "#FECACA") : T.border,
            }}
          />
        </div>

        <div style={{
          display: "flex", justifyContent: "flex-end", gap: 8, padding: "14px 24px",
          borderTop: `1px solid ${T.border}`, background: T.bg,
        }}>
          <Btn ghost onClick={onCancel}>Cancel</Btn>
          <button
            disabled={!canDelete}
            onClick={() => canDelete && onConfirm()}
            style={{
              display: "flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 999,
              border: "none", fontSize: 13.5, fontWeight: 700, cursor: canDelete ? "pointer" : "not-allowed",
              background: canDelete ? "#EF4444" : T.border, color: canDelete ? "#fff" : T.textMuted,
            }}
          >
            <Trash2 size={14} /> Delete permanently
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: T.textMuted, marginBottom: 6 }}>
        {label}
      </label>
      {children}
    </div>
  );
}

const inputStyle = {
  width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`,
  fontSize: 14, color: T.text, outline: "none", boxSizing: "border-box", fontFamily: "inherit",
};

function Btn({ children, primary, onClick, icon: Icon, style, ghost, disabled }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      display: "inline-flex", alignItems: "center", gap: 7,
      padding: "9px 18px", borderRadius: 999, fontSize: 13.5, fontWeight: 600,
      cursor: disabled ? "not-allowed" : "pointer", border: primary ? "none" : `1px solid ${T.border}`,
      background: primary ? T.primary : ghost ? "transparent" : T.surface,
      color: primary ? "#fff" : T.text, ...style,
    }}>
      {Icon && <Icon size={14} />} {children}
    </button>
  );
}

function Toggle({ on }) {
  return (
    <div style={{
      width: 36, height: 20, borderRadius: 999, background: on ? T.primary : T.border,
      position: "relative", cursor: "pointer", flexShrink: 0,
    }}>
      <div style={{
        width: 16, height: 16, borderRadius: "50%", background: "#fff", position: "absolute",
        top: 2, left: on ? 18 : 2, transition: "left .15s", boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
      }} />
    </div>
  );
}

function SliderRow({ label, value }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 12.5, color: T.textMuted }}>{value}</span>
      </div>
      <div style={{ height: 5, borderRadius: 999, background: T.border, position: "relative" }}>
        <div style={{ width: "60%", height: "100%", borderRadius: 999, background: T.primary }} />
        <div style={{
          width: 14, height: 14, borderRadius: "50%", background: "#fff", border: `2px solid ${T.primary}`,
          position: "absolute", top: -4.5, left: "58%",
        }} />
      </div>
    </div>
  );
}

function ToggleRow({ label, on }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
      <span style={{ fontSize: 13.5, color: T.text }}>{label}</span>
      <Toggle on={on} />
    </div>
  );
}

function PageNav({ back, next, go, finish }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      marginTop: 28, paddingTop: 20, borderTop: `1px solid ${T.border}`,
    }}>
      {back ? (
        <Btn ghost icon={ArrowLeft} onClick={() => go(back.page)}>{back.label}</Btn>
      ) : <div />}
      {next && (
        <Btn primary onClick={() => go(next.page)} style={{ flexDirection: "row-reverse" }}>
          {next.label} <ArrowRight size={14} style={{ marginLeft: 4 }} />
        </Btn>
      )}
      {finish && <Btn primary onClick={() => go("projects")}>Finish</Btn>}
    </div>
  );
}

function PreviewTable({ rows }) {
  return (
    <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden", marginTop: 16 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ background: T.bg }}>
            <th style={th}>ID</th><th style={th}>Response</th><th style={th}>Lang</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderTop: `1px solid ${T.border}` }}>
              <td style={td}>{r.id}</td><td style={td}>{r.text}</td><td style={td}>{r.lang}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
const th = { textAlign: "left", padding: "9px 14px", fontSize: 11.5, fontWeight: 700, color: T.textMuted, letterSpacing: "0.04em" };
const td = { padding: "9px 14px", color: T.text };

const SAMPLE_ROWS = [
  { id: "R001", text: "J'aime le goût rafraîchissant et léger.", lang: "fr" },
  { id: "R002", text: "Because it pairs well with food.", lang: "en" },
  { id: "R003", text: "C'est une habitude familiale depuis longtemps.", lang: "fr" },
  { id: "R004", text: "The price point feels fair for quality.", lang: "en" },
];

/* ---------- pages ---------- */

const INITIAL_PROJECTS = [
  { id: "sabc-may2026",  name: "SABC-MAY2026",   context: "Analyse des habitudes de consommation de boissons…", questionCount: 2, updated: "2 hours ago",  hasData: true,  archived: false },
  { id: "sabc-q1-2026",  name: "SABC-Q1-2026",   context: "Perceptions de marque auprès des 25-45 ans…",         questionCount: 4, updated: "Yesterday",     hasData: true,  archived: false },
  { id: "nps-followup",  name: "NPS-Followup",   context: "Open-ended reasons behind NPS detractor scores…",     questionCount: 1, updated: "3 days ago",    hasData: false, archived: false },
  { id: "retail-exit",   name: "Retail-Exit-24", context: "In-store exit interviews, holiday season 2024…",      questionCount: 6, updated: "2 months ago",  hasData: true,  archived: true  },
];

/* Status is derived, not stored directly:
   - Archived: an explicit, reversible user action (Archive/Unarchive) — always wins.
   - Draft: the project has no uploaded/coded data yet on any question.
   - Active: at least one question has data moving through the pipeline. */
function getProjectStatus(project) {
  if (project.archived) return "Archived";
  if (!project.hasData) return "Draft";
  return "Active";
}

const STATUS_STYLE = {
  Active:   { bg: "#ECFDF5", color: T.accent,  border: "#A7F3D0" },
  Draft:    { bg: "#FEF3C7", color: "#B45309", border: "#FDE68A" },
  Archived: { bg: T.bg,      color: T.textMuted, border: T.border },
};

function ProjectRow({ project, go, onDeleteRequest, onArchiveToggle }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const status = getProjectStatus(project);
  const st = STATUS_STYLE[status];

  return (
    <tr
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => go("context")}
      style={{ background: hovered ? "#F9FAFB" : T.surface, cursor: "pointer", borderTop: `1px solid ${T.border}` }}
    >
      <td style={{ ...td, padding: "13px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: T.primarySoft, flexShrink: 0,
            display: "flex", alignItems: "center", justifyContent: "center", color: T.primary,
          }}><Folder size={15} /></div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 700, color: T.text }}>{project.name}</div>
            <div style={{ fontSize: 12, color: T.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 340 }}>{project.context}</div>
          </div>
        </div>
      </td>
      <td style={{ ...td, color: T.textMuted, fontSize: 13 }}>{project.questionCount}</td>
      <td style={td}>
        <span
          title={
            status === "Draft" ? "No data uploaded yet on any question"
            : status === "Active" ? "At least one question has data in the pipeline"
            : "Archived — hidden from active work, not deleted"
          }
          style={{
            fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 999,
            background: st.bg, color: st.color, border: `1px solid ${st.border}`, cursor: "default",
          }}>{status.toUpperCase()}</span>
      </td>
      <td style={{ ...td, color: T.textMuted, fontSize: 12.5, whiteSpace: "nowrap" }}>{project.updated}</td>
      <td style={{ ...td, textAlign: "right" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6 }}>
          <button onClick={() => go("context")} style={{
            padding: "6px 14px", borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface,
            color: T.text, fontSize: 12.5, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap",
          }}>Open →</button>
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setMenuOpen(o => !o)}
              title="Project options"
              style={{
                width: 28, height: 28, borderRadius: 7, border: "none", background: "transparent",
                color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              }}
            ><MoreVertical size={15} /></button>
            {menuOpen && (
              <>
                <div onClick={() => setMenuOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 10 }} />
                <div style={{
                  position: "absolute", top: 30, right: 0, background: T.surface, border: `1px solid ${T.border}`,
                  borderRadius: 9, boxShadow: "0 8px 24px rgba(15,23,42,0.12)", width: 190, zIndex: 20, overflow: "hidden",
                }}>
                  <button
                    onClick={() => { setMenuOpen(false); onArchiveToggle(project); }}
                    style={{
                      display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "9px 12px",
                      border: "none", background: "transparent", color: T.text, fontSize: 13, fontWeight: 600,
                      cursor: "pointer", textAlign: "left", borderBottom: `1px solid ${T.border}`,
                    }}
                  >
                    {project.archived ? <><ArchiveRestore size={13} /> Unarchive project</> : <><Archive size={13} /> Archive project</>}
                  </button>
                  <button
                    onClick={() => { setMenuOpen(false); onDeleteRequest(project); }}
                    style={{
                      display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "9px 12px",
                      border: "none", background: "transparent", color: "#EF4444", fontSize: 13, fontWeight: 600,
                      cursor: "pointer", textAlign: "left",
                    }}
                  ><Trash2 size={13} /> Delete project</button>
                </div>
              </>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}

function ProjectsPage({ go }) {
  const [projects, setProjects] = useState(INITIAL_PROJECTS);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [toast, setToast] = useState(null); // { type: "success"|"info", message }
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [sortKey, setSortKey] = useState("updated");

  const showToast = (message) => {
    setToast(message);
    setTimeout(() => setToast(null), 4000);
  };

  const handleConfirmDelete = () => {
    setProjects(prev => prev.filter(p => p.id !== deleteTarget.id));
    showToast(`"${deleteTarget.name}" was permanently deleted.`);
    setDeleteTarget(null);
  };

  const handleArchiveToggle = (project) => {
    setProjects(prev => prev.map(p => p.id === project.id ? { ...p, archived: !p.archived } : p));
    showToast(project.archived ? `"${project.name}" was restored to active projects.` : `"${project.name}" was archived. You can unarchive it anytime — nothing was deleted.`);
  };

  const filtered = projects
    .filter(p => p.name.toLowerCase().includes(search.toLowerCase()) || p.context.toLowerCase().includes(search.toLowerCase()))
    .filter(p => statusFilter === "All" || getProjectStatus(p) === statusFilter);

  const sorted = [...filtered].sort((a, b) => {
    if (sortKey === "name") return a.name.localeCompare(b.name);
    if (sortKey === "questions") return b.questionCount - a.questionCount;
    return 0; // "updated" — keep original (most-recent-first) order
  });

  const SortHeader = ({ label, sortValue, style }) => (
    <th style={{ ...th, ...style, cursor: sortValue ? "pointer" : "default" }} onClick={() => sortValue && setSortKey(sortValue)}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        {label}
        {sortValue && sortKey === sortValue && <ChevronDown size={11} />}
      </span>
    </th>
  );

  return (
    <div style={{ padding: 28, maxWidth: 1100 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <p style={{ color: T.textMuted, fontSize: 14, margin: 0 }}>Manage coding projects across your research engagements.</p>
        <Btn primary icon={Plus} onClick={() => go("create-project")}>New Project</Btn>
      </div>

      {toast && (
        <div style={{
          display: "flex", alignItems: "center", gap: 9, padding: "10px 14px", borderRadius: 9,
          background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#166534",
          fontSize: 13, fontWeight: 600, marginBottom: 16,
        }}>
          <CheckCircle2 size={15} /> {toast}
        </div>
      )}

      {/* Search + filter bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ position: "relative" }}>
          <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: T.textMuted }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search projects…"
            style={{ ...inputStyle, paddingLeft: 30, width: 220, height: 34 }} />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ ...inputStyle, width: "auto", height: 34 }}>
          <option value="All">All statuses</option>
          <option value="Active">Active</option>
          <option value="Draft">Draft</option>
          <option value="Archived">Archived</option>
        </select>
        <span style={{ fontSize: 12.5, color: T.textMuted }}>{sorted.length} project{sorted.length !== 1 ? "s" : ""}</span>
      </div>

      {projects.length === 0 ? (
        <div style={{
          border: `1.5px dashed ${T.border}`, borderRadius: 12, padding: "48px 24px",
          textAlign: "center", color: T.textMuted,
        }}>
          <Folder size={26} style={{ opacity: 0.35, marginBottom: 10 }} />
          <p style={{ margin: "0 0 4px", fontWeight: 600, color: T.text, fontSize: 14.5 }}>No projects yet</p>
          <p style={{ margin: "0 0 16px", fontSize: 13 }}>Create a project to start coding open-ended survey responses.</p>
          <Btn primary icon={Plus} onClick={() => go("create-project")}>New Project</Btn>
        </div>
      ) : sorted.length === 0 ? (
        <div style={{ border: `1px solid ${T.border}`, borderRadius: 10, padding: "36px 24px", textAlign: "center", color: T.textMuted, fontSize: 13.5 }}>
          No projects match "{search}".
        </div>
      ) : (
        <div style={{ border: `1px solid ${T.border}`, borderRadius: 10, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: T.bg }}>
                <SortHeader label="Project" sortValue="name" />
                <SortHeader label="Questions" sortValue="questions" style={{ width: 90 }} />
                <th style={{ ...th, width: 110 }}>Status</th>
                <SortHeader label="Last updated" sortValue="updated" style={{ width: 130 }} />
                <th style={{ ...th, width: 150 }}></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(p => (
                <ProjectRow key={p.id} project={p} go={go} onDeleteRequest={setDeleteTarget} onArchiveToggle={handleArchiveToggle} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deleteTarget && (
        <DeleteProjectModal
          project={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleConfirmDelete}
        />
      )}
    </div>
  );
}

function CreateProjectPage({ go }) {
  return (
    <div style={{ padding: 28, maxWidth: 620 }}>
      <Card>
        <Field label="Project Name">
          <input style={inputStyle} placeholder="e.g. SABC-MAY2026" defaultValue="SABC-MAY2026" />
        </Field>
        <Field label="Project Context">
          <textarea style={{ ...inputStyle, minHeight: 90, resize: "vertical" }}
            defaultValue="Analyse des habitudes de consommation de boissons auprès des 18-35 ans." />
        </Field>
      </Card>
      <div style={{
        marginTop: 14, padding: "12px 16px", borderRadius: 8, background: T.bg,
        fontSize: 13, color: T.textMuted, display: "flex", gap: 9, alignItems: "flex-start",
      }}>
        <FileText size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        You can add questions after creating the project.
      </div>
      <div style={{ marginTop: 20 }}>
        <Btn primary onClick={() => go("context")}>Create Project</Btn>
      </div>
    </div>
  );
}

function ContextPage({ go }) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const project = { id: "sabc-may2026", name: "SABC-MAY2026", questionCount: 2 };

  if (deleted) {
    return (
      <div style={{ padding: 28, maxWidth: 620 }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderRadius: 10,
          background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#166534", marginBottom: 16,
        }}>
          <CheckCircle2 size={16} /> "{project.name}" was permanently deleted.
        </div>
        <Btn onClick={() => go("projects")}>Back to Projects</Btn>
      </div>
    );
  }

  return (
    <div style={{ padding: 28, maxWidth: 760, display: "flex", flexDirection: "column", gap: 16 }}>
      <Card>
        <Field label="Project Name"><input style={inputStyle} defaultValue="SABC-MAY2026" /></Field>
        <Field label="Context">
          <textarea style={{ ...inputStyle, minHeight: 80 }} defaultValue="Analyse des habitudes de consommation de boissons auprès des 18-35 ans." />
        </Field>
      </Card>
      <Card>
        <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 14px", color: T.text }}>Questions</h3>
        {[
          "Pourquoi aimez-vous cette boisson ?",
          "Qu'est-ce qui vous fait acheter la bière ?",
        ].map((q, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "12px 0", borderTop: i > 0 ? `1px solid ${T.border}` : "none",
          }}>
            <button onClick={() => go("upload")} style={{
              background: "none", border: "none", textAlign: "left", fontSize: 14, color: T.text,
              cursor: "pointer", padding: 0,
            }}>{q}</button>
            <div style={{ display: "flex", gap: 6 }}>
              <button style={iconBtn}><Edit2 size={13} /></button>
              <button style={iconBtn}><Trash2 size={13} /></button>
            </div>
          </div>
        ))}
        <div style={{ marginTop: 12 }}>
          <Btn icon={Plus} onClick={() => go("add-question")}>Add new question</Btn>
        </div>
      </Card>

      {/* Danger zone */}
      <div style={{
        background: T.surface, border: "1px solid #FECACA", borderRadius: 10, overflow: "hidden",
      }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid #FECACA", background: "#FEF2F2" }}>
          <h3 style={{ fontSize: 13.5, fontWeight: 700, margin: 0, color: "#991B1B", display: "flex", alignItems: "center", gap: 7 }}>
            <AlertTriangle size={14} /> Danger zone
          </h3>
        </div>
        <div style={{ padding: "16px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14 }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 3 }}>Delete this project</div>
            <div style={{ fontSize: 12.5, color: T.textMuted }}>Permanently removes all questions, data, and results. This cannot be undone.</div>
          </div>
          <button onClick={() => setDeleteOpen(true)} style={{
            display: "flex", alignItems: "center", gap: 7, padding: "9px 16px", borderRadius: 999,
            border: "1px solid #FECACA", background: "#fff", color: "#EF4444",
            fontSize: 13, fontWeight: 700, cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap",
          }}>
            <Trash2 size={13} /> Delete project
          </button>
        </div>
      </div>

      {deleteOpen && (
        <DeleteProjectModal
          project={project}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => { setDeleteOpen(false); setDeleted(true); }}
        />
      )}
    </div>
  );
}
const iconBtn = { width: 28, height: 28, borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" };

function AddQuestionPage({ go }) {
  return (
    <div style={{ padding: 28, maxWidth: 620 }}>
      <Card>
        <Field label="Question Text">
          <input style={inputStyle} placeholder="Pourquoi aimez-vous cette boisson ?" />
        </Field>
        <Field label="Description (optional)">
          <textarea style={{ ...inputStyle, minHeight: 70 }} placeholder="Add context for coders…" />
        </Field>
      </Card>
      <div style={{ marginTop: 20 }}><Btn primary>Save Question</Btn></div>
      <PageNav back={{ page: "context", label: "Back to Project Context" }} next={{ page: "upload", label: "Upload" }} go={go} />
    </div>
  );
}

function UploadPage({ go }) {
  const [fileName] = useState("SABC-MAY2026_responses.xlsx");
  const [status]    = useState("uploaded"); // uploaded | processing | error

  return (
    <div style={{ padding: 28, maxWidth: 820 }}>
      <div style={{
        border: `2px dashed ${T.border}`, borderRadius: 12, padding: "32px 24px",
        textAlign: "center", color: T.textMuted, background: T.surface, marginBottom: 12,
      }}>
        <UploadIcon size={24} style={{ color: T.primary, marginBottom: 8 }} />
        <p style={{ margin: "0 0 4px", fontWeight: 600, color: T.text, fontSize: 14 }}>Drop XLSX/CSV here</p>
        <p style={{ margin: 0, fontSize: 12.5 }}>or click to browse</p>
      </div>

      {/* File name + upload status */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 9,
        background: status === "uploaded" ? "#ECFDF5" : T.bg,
        border: `1px solid ${status === "uploaded" ? "#A7F3D0" : T.border}`, marginBottom: 18,
      }}>
        <FileText size={15} style={{ color: status === "uploaded" ? T.accent : T.textMuted, flexShrink: 0 }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: T.text, flex: 1 }}>{fileName}</span>
        <span style={{
          display: "flex", alignItems: "center", gap: 5, fontSize: 11.5, fontWeight: 700,
          color: status === "uploaded" ? T.accent : T.textMuted,
        }}>
          {status === "uploaded" && <CheckCircle2 size={13} />}
          {status === "uploaded" ? "Uploaded successfully" : "Processing…"}
        </span>
      </div>

      <Card style={{ marginBottom: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <Field label="Sheet"><select style={inputStyle}><option>Responses</option></select></Field>
          <Field label="Response Column"><select style={inputStyle}><option>Q1_text</option></select></Field>
          <Field label="ID Column"><select style={inputStyle}><option>respondent_id</option></select></Field>
        </div>
      </Card>
      <h4 style={{ fontSize: 12.5, fontWeight: 700, color: T.textMuted, letterSpacing: "0.04em", margin: "0 0 4px" }}>PREVIEW — FIRST 50 ROWS</h4>
      <PreviewTable rows={SAMPLE_ROWS} />
      <PageNav back={{ page: "add-question", label: "Question Details" }} next={{ page: "preprocess", label: "Preprocess" }} go={go} />
    </div>
  );
}

function PreprocessPage({ go }) {
  const [stage, setStage] = useState("setup"); // "setup" | "running" | "done"

  const handleRun = () => {
    setStage("running");
    setTimeout(() => setStage("done"), 900);
  };

  const done = stage === "done";

  return (
    <div style={{ padding: 28, maxWidth: 980 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 18 }}>
        <Card>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 16px" }}>Cleaning</h3>
          <SliderRow label="Minimum word count" value="3 words" />
          <p style={{ margin: "-10px 0 16px", fontSize: 11.5, color: T.textMuted, lineHeight: 1.4 }}>
            Responses shorter than this are treated as too thin to code meaningfully and are excluded (e.g. "ok", "n/a"). Most projects use 2–5 words.
          </p>
          <ToggleRow label="Remove emojis" on />
          <ToggleRow label="Replace URLs" on />
          <ToggleRow label="Normalize text" on />
          <ToggleRow label="Detect duplicates & preserve count" on />
          <p style={{ margin: "-10px 0 0", fontSize: 11.5, color: T.textMuted, lineHeight: 1.4 }}>
            Duplicate responses are grouped for coding (to reduce cost) but their original count is kept for accurate frequency reporting.
          </p>
        </Card>
        <Card>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 16px" }}>Translation</h3>

          <div style={{
            display: "flex", gap: 8, alignItems: "flex-start", padding: "9px 11px",
            borderRadius: 8, background: T.bg, marginBottom: 16,
          }}>
            <Languages size={13} style={{ color: T.textMuted, flexShrink: 0, marginTop: 1 }} />
            <span style={{ fontSize: 11.5, color: T.textMuted, lineHeight: 1.5 }}>
              Example: your survey was conducted in French. Set <strong style={{ color: T.text }}>Detect responses in</strong> to English to catch respondents who answered in English, and they'll be translated into <strong style={{ color: T.text }}>Translate into (survey language)</strong>.
            </span>
          </div>

          <Field label="Detect responses in">
            <select style={inputStyle}><option>English</option></select>
          </Field>
          <p style={{ margin: "-10px 0 16px", fontSize: 11.5, color: T.textMuted, lineHeight: 1.4 }}>
            The language a response was <strong>written in</strong> — responses matching this are flagged for translation.
          </p>

          <Field label="Translate into (survey language)">
            <select style={inputStyle}><option>French</option></select>
          </Field>
          <p style={{ margin: "-10px 0 16px", fontSize: 11.5, color: T.textMuted, lineHeight: 1.4 }}>
            The language your survey was <strong>asked in</strong> — detected responses are translated <strong>into</strong> this language.
          </p>

          <Field label="Codebook language">
            <select style={inputStyle}><option>French</option></select>
          </Field>
          <p style={{ margin: "-10px 0 16px", fontSize: 11.5, color: T.textMuted, lineHeight: 1.4 }}>
            The language your final codes and definitions will be written in. Defaults to French.
          </p>

          <ToggleRow label="Auto-translate" on />
        </Card>
      </div>

      {/* ── State 1: setup-only, Run Preprocessing is the sole primary action ── */}
      {!done && (
        <Card style={{ marginBottom: 18 }}>
          <Btn primary icon={stage === "running" ? null : Sliders} onClick={handleRun}
            disabled={stage === "running"}
            style={{ width: "100%", justifyContent: "center", opacity: stage === "running" ? 0.75 : 1 }}>
            {stage === "running" ? "Running preprocessing…" : "Run Preprocessing"}
          </Btn>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: T.textMuted, textAlign: "center" }}>
            Cleaning and translation settings above will be applied to all uploaded responses.
          </p>
        </Card>
      )}

      {/* ── State 2: results revealed after preprocessing runs ── */}
      {done && (
        <>
          <Card style={{ marginBottom: 18 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <CheckCircle2 size={16} style={{ color: T.accent }} />
                <span style={{ fontSize: 13.5, fontWeight: 700, color: T.text }}>Preprocessing complete</span>
              </div>
              <button onClick={handleRun} style={{
                display: "flex", alignItems: "center", gap: 6, border: `1px solid ${T.border}`, background: T.surface,
                color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "6px 12px", borderRadius: 7,
              }}><RotateCcw size={12} /> Re-run with new settings</button>
            </div>
            <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
              <Stat label="Loaded" value="7" />
              <Stat label="Remaining" value="6" />
              <Stat label="Removed" value="1" />
              <Stat label="Languages" value="fr:4, en:2" />
            </div>
          </Card>

          <h4 style={{ fontSize: 12.5, fontWeight: 700, color: T.textMuted, letterSpacing: "0.04em", margin: "0 0 4px" }}>PREVIEW — CLEANED RESPONSES</h4>
          <PreviewTable rows={SAMPLE_ROWS} />
        </>
      )}

      <PageNav back={{ page: "upload", label: "Upload" }} next={done ? { page: "code", label: "Code" } : null} go={go} />
    </div>
  );
}
function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11.5, color: T.textMuted, fontWeight: 600, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 700, color: T.text }}>{value}</div>
    </div>
  );
}

function CodePage({ go, onCodingComplete }) {
  const [mode, setMode] = useState("ai");
  const [running, setRunning] = useState(false);

  const handleRun = () => {
    setRunning(true);
    // Coding now routes to QA Review first, not straight to Results —
    // the researcher should approve the meaning before it's called final.
    setTimeout(() => { onCodingComplete?.(); go("qa"); }, 900);
  };

  return (
    <div style={{ padding: 28, maxWidth: 760 }}>
      <div style={{ display: "inline-flex", padding: 4, background: T.bg, borderRadius: 999, marginBottom: 20 }}>
        {[["ai", "AI-generated coding", Sparkles], ["book", "Use existing codebook", BookOpen]].map(([k, l, Icon]) => (
          <button key={k} onClick={() => setMode(k)} style={{
            display: "flex", alignItems: "center", gap: 7, padding: "8px 18px", borderRadius: 999,
            border: "none", cursor: "pointer", fontSize: 13.5, fontWeight: 600,
            background: mode === k ? T.surface : "transparent",
            color: mode === k ? T.primary : T.textMuted,
            boxShadow: mode === k ? "0 1px 2px rgba(16,24,40,0.08)" : "none",
          }}><Icon size={14} /> {l}</button>
        ))}
      </div>

      {mode === "ai" ? (
        <Card>
          <SliderRow label="Group similar answers tightly" value="Medium" />
          <p style={{ margin: "-12px 0 16px", fontSize: 11.5, color: T.textMuted }}>Higher = fewer, broader codes. Lower = more, narrower codes.</p>
          <SliderRow label="Number of themes to create" value="12–18 codes" />
          <p style={{ margin: "-12px 0 16px", fontSize: 11.5, color: T.textMuted }}>How many distinct codes the AI should aim for.</p>
          <SliderRow label="Examples used per theme" value="5" />
          <p style={{ margin: "-12px 0 16px", fontSize: 11.5, color: T.textMuted }}>How many sample responses the AI reviews before naming each code.</p>
          <ToggleRow label="Allow more than one code per response" on />
          <Field label="Target code count"><input style={inputStyle} defaultValue="15" /></Field>
          <Btn primary icon={running ? null : Sparkles} onClick={handleRun} style={{ opacity: running ? 0.7 : 1 }}>
            {running ? "Running AI coding…" : "Run AI Coding → Review Codebook"}
          </Btn>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: T.textMuted, display: "flex", alignItems: "center", gap: 6 }}>
            <ShieldCheck size={13} style={{ color: T.textMuted, flexShrink: 0 }} />
            You'll review the codebook and flag anything uncertain before results are final.
          </p>
        </Card>
      ) : (
        <Card>
          <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
            <Btn icon={UploadIcon}>Upload codebook</Btn>
            <Btn icon={FileText}>Preview codebook</Btn>
          </div>
          <Field label="Code label column"><select style={inputStyle}><option>code_name</option></select></Field>
          <Field label="Definition column"><select style={inputStyle}><option>definition</option></select></Field>
          <Field label="Grouping column"><select style={inputStyle}><option>theme</option></select></Field>
          <Btn primary icon={running ? null : BookOpen} onClick={handleRun} style={{ opacity: running ? 0.7 : 1 }}>
            {running ? "Running codebook coding…" : "Run Codebook Coding → Review Codebook"}
          </Btn>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: T.textMuted, display: "flex", alignItems: "center", gap: 6 }}>
            <ShieldCheck size={13} style={{ color: T.textMuted, flexShrink: 0 }} />
            You'll review the codebook and flag anything uncertain before results are final.
          </p>
        </Card>
      )}
      <PageNav back={{ page: "preprocess", label: "Preprocess" }} next={{ page: "qa", label: "QA Review" }} go={go} />
    </div>
  );
}

const ALL_CODES = [
  "Taste & refreshment", "Price & value", "Affordability", "Family habit",
  "Brand loyalty", "Health perception", "Social occasion", "Packaging",
  "Availability", "Quality perception",
];

const SURVEY_CORPUS = [
  "J'aime le goût rafraîchissant et léger.",
  "Because it pairs well with food.",
  "C'est une habitude familiale depuis longtemps.",
  "The price point feels fair for quality.",
  "Le goût est doux et pas trop sucré.",
  "It's refreshing on a hot day.",
  "I always buy it because my parents did.",
  "Easy to find in every store nearby.",
  "Feels like a treat for social gatherings with friends.",
  "Good value compared to other brands.",
];

function CodeChip({ label, onRemove }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 6px 5px 12px",
      borderRadius: 999, background: T.primarySoft, color: T.primary, fontSize: 12.5, fontWeight: 600,
    }}>
      {label}
      <button onClick={onRemove} style={{
        width: 16, height: 16, borderRadius: "50%", border: "none", background: "rgba(58,95,255,0.15)",
        color: T.primary, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", padding: 0,
      }}><X size={10} /></button>
    </span>
  );
}

function CodeMultiSelect({ label, selected, setSelected, exclude = [] }) {
  const [open, setOpen] = useState(false);
  const options = ALL_CODES.filter(c => !selected.includes(c) && !exclude.includes(c));
  return (
    <div style={{ marginBottom: 16, position: "relative" }}>
      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: T.textMuted, marginBottom: 6 }}>{label}</label>
      <div style={{
        ...inputStyle, minHeight: 42, height: "auto", display: "flex", flexWrap: "wrap", gap: 6,
        alignItems: "center", cursor: "text", paddingTop: selected.length ? 8 : 9, paddingBottom: selected.length ? 8 : 9,
      }} onClick={() => setOpen(o => !o)}>
        {selected.map(s => (
          <CodeChip key={s} label={s} onRemove={() => setSelected(selected.filter(x => x !== s))} />
        ))}
        {selected.length === 0 && <span style={{ color: T.textMuted, fontSize: 13.5 }}>Click to select codes…</span>}
      </div>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0, marginTop: 4, background: T.surface,
          border: `1px solid ${T.border}`, borderRadius: 8, boxShadow: "0 6px 16px rgba(16,24,40,0.10)",
          zIndex: 10, maxHeight: 220, overflow: "auto",
        }}>
          {options.length === 0 && <div style={{ padding: "10px 14px", fontSize: 13, color: T.textMuted }}>No more codes</div>}
          {options.map(c => (
            <button key={c} onClick={(e) => { e.stopPropagation(); setSelected([...selected, c]); }} style={{
              display: "block", width: "100%", textAlign: "left", padding: "9px 14px", border: "none",
              background: "transparent", fontSize: 13.5, color: T.text, cursor: "pointer",
            }}
              onMouseEnter={(e) => e.currentTarget.style.background = T.bg}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >{c}</button>
          ))}
        </div>
      )}
    </div>
  );
}

function SuggestionRow({ text, status, onAccept, onReject }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
      padding: "10px 12px", borderRadius: 8, fontSize: 13,
      border: `1px solid ${status === "accepted" ? T.accent : status === "rejected" ? T.border : T.border}`,
      background: status === "accepted" ? "#ECFDF5" : status === "rejected" ? T.bg : T.surface,
      opacity: status === "rejected" ? 0.55 : 1,
    }}>
      <span style={{
        color: T.text, textDecoration: status === "rejected" ? "line-through" : "none",
      }}>{text}</span>
      {status === "pending" ? (
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button onClick={onAccept} title="Accept" style={{
            width: 26, height: 26, borderRadius: 7, border: `1px solid ${T.accent}`, background: "#fff",
            color: T.accent, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          }}><ThumbsUp size={12} /></button>
          <button onClick={onReject} title="Reject" style={{
            width: 26, height: 26, borderRadius: 7, border: `1px solid #EF4444`, background: "#fff",
            color: "#EF4444", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          }}><ThumbsDown size={12} /></button>
        </div>
      ) : (
        <span style={{
          fontSize: 11, fontWeight: 700, flexShrink: 0, letterSpacing: "0.03em",
          color: status === "accepted" ? T.accent : T.textMuted,
        }}>{status === "accepted" ? "ACCEPTED" : "REJECTED"}</span>
      )}
    </div>
  );
}

/* Suggestion card with name, AI-written definition, and example verbatims pulled
   from the original survey responses — used for AI-generated split sub-codes. */
function CodebookSuggestionCard({ code, onAccept, onReject }) {
  return (
    <div style={{
      borderRadius: 9, fontSize: 13,
      border: `1px solid ${code.status === "accepted" ? T.accent : T.border}`,
      background: code.status === "accepted" ? "#ECFDF5" : code.status === "rejected" ? T.bg : T.surface,
      opacity: code.status === "rejected" ? 0.55 : 1,
      overflow: "hidden",
    }}>
      <div style={{ padding: "11px 13px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: code.status === "rejected" ? 0 : 8 }}>
          <span style={{
            fontWeight: 700, color: T.text, fontSize: 13.5,
            textDecoration: code.status === "rejected" ? "line-through" : "none",
          }}>{code.name}</span>
          {code.status === "pending" ? (
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              <button onClick={onAccept} title="Accept" style={{
                width: 26, height: 26, borderRadius: 7, border: `1px solid ${T.accent}`, background: "#fff",
                color: T.accent, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              }}><ThumbsUp size={12} /></button>
              <button onClick={onReject} title="Reject" style={{
                width: 26, height: 26, borderRadius: 7, border: `1px solid #EF4444`, background: "#fff",
                color: "#EF4444", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              }}><ThumbsDown size={12} /></button>
            </div>
          ) : (
            <span style={{
              fontSize: 10.5, fontWeight: 700, flexShrink: 0, letterSpacing: "0.03em",
              color: code.status === "accepted" ? T.accent : T.textMuted,
            }}>{code.status === "accepted" ? "ACCEPTED" : "REJECTED"}</span>
          )}
        </div>
        {code.status !== "rejected" && (
          <>
            <p style={{ margin: "0 0 9px", fontSize: 12.5, color: T.textMuted, lineHeight: 1.45 }}>{code.definition}</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {code.examples.map((ex, i) => (
                <div key={i} style={{
                  fontSize: 12, color: T.text, background: T.bg, borderRadius: 6,
                  padding: "6px 9px", fontStyle: "italic", borderLeft: `2px solid ${T.primary}`,
                }}>"{ex}"</div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* Manual sub-code row: name + definition (own words or AI-generated) + examples,
   each pulled or written independently per code. */
function ManualSubcodeRow({ index, code, onChange, onRemove, removable, onGenerateDefinition, generating }) {
  return (
    <div style={{ border: `1px solid ${T.border}`, borderRadius: 9, padding: 12, marginBottom: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 9 }}>
        <span style={{
          width: 20, height: 20, borderRadius: "50%", background: T.bg, color: T.textMuted,
          fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>{index + 1}</span>
        <input
          style={{ ...inputStyle, flex: 1 }}
          placeholder="New sub-code name…"
          value={code.name}
          onChange={(e) => onChange({ ...code, name: e.target.value })}
        />
        <button onClick={onRemove} disabled={!removable} style={{
          width: 30, height: 30, borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface,
          color: !removable ? "#D1D5DB" : T.textMuted, cursor: !removable ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}><Trash2 size={13} /></button>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: code.examples.length ? 9 : 0 }}>
        <textarea
          style={{ ...inputStyle, flex: 1, minHeight: 56, resize: "vertical", fontSize: 12.5 }}
          placeholder="Definition — what does this code capture?"
          value={code.definition}
          onChange={(e) => onChange({ ...code, definition: e.target.value })}
        />
        <button onClick={onGenerateDefinition} disabled={!code.name.trim() || generating} title="Generate definition with AI" style={{
          display: "flex", alignItems: "center", gap: 5, flexShrink: 0, padding: "8px 10px",
          borderRadius: 7, border: `1px solid ${T.primary}`, background: "#fff", color: T.primary,
          fontSize: 11.5, fontWeight: 600, cursor: (!code.name.trim() || generating) ? "not-allowed" : "pointer",
          opacity: (!code.name.trim() || generating) ? 0.5 : 1, whiteSpace: "nowrap",
        }}>
          <Sparkles size={12} /> {generating ? "Generating…" : "AI generate"}
        </button>
      </div>

      {code.examples.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {code.examples.map((ex, i) => (
            <div key={i} style={{
              fontSize: 12, color: T.text, background: T.bg, borderRadius: 6,
              padding: "6px 9px", fontStyle: "italic", borderLeft: `2px solid ${T.primary}`,
            }}>"{ex}"</div>
          ))}
        </div>
      )}
    </div>
  );
}

function SplitPanel({ go, onOperation }) {
  const [mode, setMode] = useState("ai");

  /* ── AI state ── */
  const [aiSourceCodes, setAiSourceCodes] = useState(["Taste & refreshment"]);
  const [targetCount,   setTargetCount]   = useState(3);
  const [aiGenerated,   setAiGenerated]   = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState([]);
  const [generating,    setGenerating]    = useState(false);

  const SUBCODE_LIBRARY = [
    { name: "Refreshing taste",      definition: "Mentions of the drink feeling crisp, light, or thirst-quenching in warm-weather contexts.", examples: [SURVEY_CORPUS[0], SURVEY_CORPUS[5]] },
    { name: "Light / not heavy",     definition: "References to a mild, non-cloying flavor that doesn't feel overly sweet or filling.",       examples: [SURVEY_CORPUS[4]] },
    { name: "Crisp / carbonation",   definition: "Comments specifically about fizz, bubbles, or the carbonated mouthfeel.",                   examples: [SURVEY_CORPUS[5]] },
    { name: "Sweetness level",       definition: "Opinions on how sweet or balanced the drink tastes relative to expectations.",               examples: [SURVEY_CORPUS[4]] },
    { name: "Smooth finish",         definition: "Descriptions of the aftertaste or how the drink finishes on the palate.",                    examples: [SURVEY_CORPUS[0]] },
    { name: "Natural flavor",        definition: "Perceptions that the taste is natural rather than artificial.",                               examples: [SURVEY_CORPUS[4]] },
  ];

  const handleGenerate = () => {
    setGenerating(true);
    setAiGenerated(false);
    setTimeout(() => {
      setAiSuggestions(SUBCODE_LIBRARY.slice(0, targetCount).map((c, i) => ({ id: i + 1, ...c, status: "pending" })));
      setAiGenerated(true);
      setGenerating(false);
    }, 800);
  };

  const setAiStatus   = (id, s) => setAiSuggestions(prev => prev.map(x => x.id === id ? { ...x, status: s } : x));
  const aiAccepted    = aiSuggestions.filter(s => s.status === "accepted");
  const aiPending     = aiSuggestions.filter(s => s.status === "pending").length;

  /* ── Manual state ── */
  const [manualSourceCodes, setManualSourceCodes] = useState(["Taste & refreshment"]);
  const [manualCodes,       setManualCodes]       = useState([{ id: "m1", name: "", definition: "", examples: [] }]);
  const [generatingId,      setGeneratingId]      = useState(null);

  const updateManualRow = (id, upd) => setManualCodes(prev => prev.map(m => m.id === id ? { ...upd, id } : m));
  const addManualRow    = () => setManualCodes(prev => [...prev, { id: `m${Date.now()}`, name: "", definition: "", examples: [] }]);
  const removeManualRow = (id) => setManualCodes(prev => prev.filter(m => m.id !== id));

  const generateManualDef = (id) => {
    setGeneratingId(id);
    setTimeout(() => {
      setManualCodes(prev => prev.map(m => m.id === id ? {
        ...m,
        definition: `Responses referencing "${m.name.toLowerCase()}" as a reason tied to ${manualSourceCodes[0]?.toLowerCase() || "the parent code"}.`,
        examples: [SURVEY_CORPUS[Math.floor(Math.random() * SURVEY_CORPUS.length)]],
      } : m));
      setGeneratingId(null);
    }, 700);
  };

  const manualFilled = manualCodes.filter(m => m.name.trim() !== "").length;

  const MODE_META = {
    ai: { label: "AI split", Icon: Sparkles, desc: "Describe how many sub-codes you need — AI names, defines, and finds examples for each." },
    manual: { label: "Manual split", Icon: Edit2, desc: "Name each sub-code yourself and write definitions, or ask AI to draft them for you." },
  };

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 20px", borderBottom: `1px solid ${T.border}`, background: T.bg }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: T.primarySoft, display: "flex", alignItems: "center", justifyContent: "center", color: T.primary }}>
          <Scissors size={15} />
        </div>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: T.text }}>Split a code</h3>
          <p style={{ margin: 0, fontSize: 12, color: T.textMuted }}>Break one code into focused sub-codes</p>
        </div>
      </div>

      <div style={{ padding: "18px 20px" }}>
        {/* Mode toggle with descriptions */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 20 }}>
          {Object.entries(MODE_META).map(([k, { label, Icon, desc }]) => (
            <button key={k} onClick={() => setMode(k)} style={{
              padding: "10px 12px", borderRadius: 9, textAlign: "left", cursor: "pointer",
              border: mode === k ? `2px solid ${T.primary}` : `1px solid ${T.border}`,
              background: mode === k ? T.primarySoft : T.surface,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <Icon size={13} style={{ color: mode === k ? T.primary : T.textMuted }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: mode === k ? T.primary : T.text }}>{label}</span>
              </div>
              <span style={{ fontSize: 11.5, color: T.textMuted, lineHeight: 1.4 }}>{desc}</span>
            </button>
          ))}
        </div>

        {mode === "ai" ? (
          <div>
            <CodeMultiSelect label="Code(s) to split" selected={aiSourceCodes}
              setSelected={v => { setAiSourceCodes(v); setAiGenerated(false); }} />

            <Field label="Number of sub-codes to generate">
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 0, border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden" }}>
                  <button onClick={() => { setTargetCount(c => Math.max(2, c-1)); setAiGenerated(false); }}
                    style={{ width: 32, height: 36, border: "none", background: T.bg, color: T.text, fontSize: 16, cursor: "pointer", fontWeight: 700 }}>−</button>
                  <span style={{ width: 40, textAlign: "center", fontSize: 15, fontWeight: 700, color: T.text }}>{targetCount}</span>
                  <button onClick={() => { setTargetCount(c => Math.min(6, c+1)); setAiGenerated(false); }}
                    style={{ width: 32, height: 36, border: "none", background: T.bg, color: T.text, fontSize: 16, cursor: "pointer", fontWeight: 700 }}>+</button>
                </div>
                <span style={{ fontSize: 12, color: T.textMuted }}>sub-codes. AI will define each and pull matching survey examples.</span>
              </div>
            </Field>

            {/* Primary CTA */}
            <button onClick={handleGenerate} disabled={aiSourceCodes.length === 0 || generating}
              style={{
                width: "100%", padding: "11px 0", borderRadius: 9, border: "none", cursor: "pointer",
                background: aiSourceCodes.length === 0 ? T.border : T.primary, color: "#fff",
                fontSize: 14, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                marginBottom: 18, opacity: generating ? 0.8 : 1,
              }}>
              <Sparkles size={15} />
              {generating ? "Generating sub-codes…" : aiGenerated ? "Regenerate suggestions" : "Generate split suggestions"}
            </button>

            {!aiGenerated && !generating && (
              <div style={{ textAlign: "center", padding: "20px 0", color: T.textMuted, fontSize: 13 }}>
                <Sparkles size={22} style={{ marginBottom: 8, opacity: 0.3, display: "block", margin: "0 auto 8px" }} />
                Select a code and click Generate — AI will suggest {targetCount} sub-codes with definitions and survey examples.
              </div>
            )}

            {generating && (
              <div style={{ textAlign: "center", padding: "20px 0", color: T.textMuted, fontSize: 13 }}>
                <div style={{ fontSize: 22, marginBottom: 8 }}>⟳</div>
                Analysing "{aiSourceCodes[0]}" across {SURVEY_CORPUS.length} responses…
              </div>
            )}

            {aiGenerated && (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: T.text }}>Review suggestions</span>
                  <span style={{ fontSize: 11.5, color: T.textMuted }}>
                    {aiAccepted.length} accepted{aiPending > 0 ? `, ${aiPending} pending` : ""}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
                  {aiSuggestions.map(s => (
                    <CodebookSuggestionCard key={s.id} code={s}
                      onAccept={() => setAiStatus(s.id, "accepted")}
                      onReject={() => setAiStatus(s.id, "rejected")} />
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          <div>
            <CodeMultiSelect label="Code(s) to split" selected={manualSourceCodes} setSelected={setManualSourceCodes} />
            {manualSourceCodes.length > 1 && (
              <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 12, fontSize: 12, color: T.textMuted }}>
                <Layers size={12} /> Sub-codes below will apply to all {manualSourceCodes.length} selected codes.
              </div>
            )}
            <div style={{ fontSize: 12.5, fontWeight: 700, color: T.textMuted, marginBottom: 8, letterSpacing: "0.03em" }}>SUB-CODES</div>
            <div>
              {manualCodes.map((m, i) => (
                <ManualSubcodeRow key={m.id} index={i} code={m}
                  onChange={upd => updateManualRow(m.id, upd)}
                  onRemove={() => removeManualRow(m.id)}
                  removable={manualCodes.length > 1}
                  onGenerateDefinition={() => generateManualDef(m.id)}
                  generating={generatingId === m.id} />
              ))}
            </div>
            <button onClick={addManualRow} style={{
              display: "flex", alignItems: "center", gap: 6, border: `1px dashed ${T.border}`, borderRadius: 8,
              background: "transparent", color: T.primary, fontSize: 12.5, fontWeight: 600,
              cursor: "pointer", padding: "8px 12px", width: "100%", marginBottom: 18,
            }}><Plus size={13} /> Add another sub-code</button>
          </div>
        )}

        {/* Footer actions */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 16, borderTop: `1px solid ${T.border}`, marginTop: 4 }}>
<div />
          <button
            disabled={mode === "ai" ? (!aiGenerated || aiAccepted.length === 0) : (manualSourceCodes.length === 0 || manualFilled === 0)}
            onClick={() => {
              const op = mode === "ai"
                ? { type: "split", mode: "ai", codes: aiSourceCodes, subCodes: aiAccepted.map(s => s.name) }
                : { type: "split", mode: "manual", codes: manualSourceCodes, subCodes: manualCodes.filter(m=>m.name.trim()).map(m=>m.name) };
              onOperation?.(op); go?.("results");
            }}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "10px 20px", borderRadius: 9,
              border: "none", fontSize: 13.5, fontWeight: 700, cursor: "pointer",
              background: (mode === "ai" ? (!aiGenerated || aiAccepted.length === 0) : (manualSourceCodes.length === 0 || manualFilled === 0))
                ? T.border : T.primary,
              color: "#fff",
            }}>
            Apply split <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function MergePanel({ go, onOperation }) {
  const [sourceCodes, setSourceCodes] = useState(["Price & value", "Affordability"]);
  const [mergedName,  setMergedName]  = useState("Price & value");
  const [aiSuggestions, setAiSuggestions] = useState([
    { id: 1, a: "Price & value",   b: "Affordability",       pct: 78, strength: "strong",  status: "pending" },
    { id: 2, a: "Brand loyalty",   b: "Quality perception",  pct: 64, strength: "moderate", status: "pending" },
    { id: 3, a: "Technical Issues",b: "Usability Issues",    pct: 41, strength: "weak",    status: "pending" },
  ]);

  const setStatus = (id, s) => setAiSuggestions(prev => prev.map(x => x.id === id ? { ...x, status: s } : x));
  const acceptSuggestion = (s) => {
    setStatus(s.id, "accepted");
    setSourceCodes(prev => Array.from(new Set([...prev, s.a, s.b])));
    if (!mergedName || mergedName === "Price & value") setMergedName(s.a);
  };

  const strengthColor = { strong: T.accent, moderate: "#F59E0B", weak: T.textMuted };
  const strengthBg    = { strong: "#ECFDF5", moderate: "#FEF3C7", weak: T.bg };
  const strengthBorder= { strong: "#A7F3D0", moderate: "#FDE68A", weak: T.border };

  // preview: list of "survivor" codes from the merge
  const previewItems = sourceCodes.length >= 2
    ? [`"${mergedName}" (merged — ${sourceCodes.length} codes combined)`,
       ...ALL_CODES.filter(c => !sourceCodes.includes(c)).slice(0, 3).map(c => `"${c}" (unchanged)`)]
    : [];

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 20px", borderBottom: `1px solid ${T.border}`, background: T.bg }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: "#F5F3FF", display: "flex", alignItems: "center", justifyContent: "center", color: "#8B5CF6" }}>
          <GitMerge size={15} />
        </div>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: T.text }}>Merge codes</h3>
          <p style={{ margin: 0, fontSize: 12, color: T.textMuted }}>Combine overlapping codes into one</p>
        </div>
      </div>

      <div style={{ padding: "18px 20px" }}>
        <CodeMultiSelect label="Codes to merge" selected={sourceCodes} setSelected={setSourceCodes} />

        {/* Merged name */}
        {sourceCodes.length >= 2 && (
          <Field label="Resulting code name">
            <div style={{ position: "relative" }}>
              <input style={{ ...inputStyle, fontWeight: 700, fontSize: 14, paddingRight: 36 }}
                value={mergedName} onChange={e => setMergedName(e.target.value)} />
              <Edit2 size={13} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: T.textMuted, pointerEvents: "none" }} />
            </div>
          </Field>
        )}

        {/* Preview */}
        {sourceCodes.length >= 2 && (
          <div style={{ marginBottom: 18, padding: "10px 12px", borderRadius: 9, background: "#F5F3FF", border: "1px solid #DDD6FE" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#7C3AED", marginBottom: 7, letterSpacing: "0.04em" }}>PREVIEW — CODEBOOK AFTER MERGE</div>
            {previewItems.map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4, fontSize: 12, color: i === 0 ? "#7C3AED" : T.textMuted, fontWeight: i === 0 ? 700 : 400 }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: i === 0 ? "#8B5CF6" : T.border, flexShrink: 0 }} />
                {item}
              </div>
            ))}
            {ALL_CODES.filter(c => !sourceCodes.includes(c)).length > 3 && (
              <div style={{ fontSize: 11.5, color: T.textMuted, marginTop: 2 }}>+ {ALL_CODES.filter(c => !sourceCodes.includes(c)).length - 3} other codes unchanged</div>
            )}
          </div>
        )}

        {/* AI Suggestions */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: T.textMuted, marginBottom: 10, letterSpacing: "0.03em" }}>AI MERGE SUGGESTIONS</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {aiSuggestions.map(s => (
              <div key={s.id} style={{
                borderRadius: 9, border: `1px solid ${s.status === "accepted" ? "#A7F3D0" : s.status === "rejected" ? T.border : T.border}`,
                background: s.status === "accepted" ? "#ECFDF5" : s.status === "rejected" ? T.bg : T.surface,
                opacity: s.status === "rejected" ? 0.5 : 1, overflow: "hidden",
              }}>
                <div style={{ padding: "10px 12px", display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: s.status === "rejected" ? T.textMuted : T.text,
                        textDecoration: s.status === "rejected" ? "line-through" : "none" }}>
                        "{s.a}" + "{s.b}"
                      </span>
                      <span style={{ fontSize: 10.5, fontWeight: 700, padding: "1px 7px", borderRadius: 999,
                        background: strengthBg[s.strength], color: strengthColor[s.strength],
                        border: `1px solid ${strengthBorder[s.strength]}` }}>
                        {s.strength} match
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: T.textMuted }}>
                      {s.pct}% co-occurrence across responses — {
                        s.strength === "strong" ? "highly likely to refer to the same concept" :
                        s.strength === "moderate" ? "partial thematic overlap" :
                        "low overlap — consider before merging"
                      }
                    </div>
                  </div>
                  {s.status === "pending" ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, flexShrink: 0 }}>
                      <button onClick={() => acceptSuggestion(s)} title="Accept merge suggestion"
                        style={{ display: "flex", alignItems: "center", gap: 4, padding: "5px 10px", borderRadius: 6, border: `1px solid ${T.accent}`, background: "#fff", color: T.accent, fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}>
                        <ThumbsUp size={11} /> Accept
                      </button>
                      <button onClick={() => setStatus(s.id, "rejected")} title="Reject merge suggestion"
                        style={{ display: "flex", alignItems: "center", gap: 4, padding: "5px 10px", borderRadius: 6, border: "1px solid #FECACA", background: "#fff", color: "#EF4444", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}>
                        <ThumbsDown size={11} /> Reject
                      </button>
                    </div>
                  ) : (
                    <span style={{ fontSize: 11, fontWeight: 700, color: s.status === "accepted" ? T.accent : T.textMuted, flexShrink: 0 }}>
                      {s.status === "accepted" ? "✓ ACCEPTED" : "REJECTED"}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
<div />
          <button
            disabled={sourceCodes.length < 2}
            onClick={() => { onOperation?.({ type: "merge", codes: sourceCodes, mergedName }); go?.("results"); }}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "10px 20px", borderRadius: 9, border: "none",
              fontSize: 13.5, fontWeight: 700, cursor: sourceCodes.length < 2 ? "not-allowed" : "pointer",
              background: sourceCodes.length < 2 ? T.border : "#8B5CF6", color: "#fff",
            }}>
            Apply merge <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function RefinementPage({ go, onOperation }) {
  const [tool, setTool] = useState(null); // null | "split" | "merge"

  const TOOLS = [
    {
      id: "split", Icon: Scissors, color: T.primary, bg: T.primarySoft, border: "#C7D2FE",
      title: "Split a broad code", desc: "Break one code into several focused sub-codes.",
    },
    {
      id: "merge", Icon: GitMerge, color: "#8B5CF6", bg: "#F5F3FF", border: "#DDD6FE",
      title: "Merge overlapping codes", desc: "Combine codes that mean the same thing into one.",
    },
    {
      id: "rename", Icon: Edit2, color: "#F59E0B", bg: "#FEF3C7", border: "#FDE68A",
      title: "Rename / edit a code", desc: "Update a code's name or definition without changing its data.", disabled: true,
    },
    {
      id: "lowconf", Icon: MessageSquareWarning, color: "#EF4444", bg: "#FEF2F2", border: "#FECACA",
      title: "Review low-confidence responses", desc: "Jump to responses the AI was least sure about.", link: "qa",
    },
  ];

  if (tool === "split") {
    return (
      <div style={{ padding: 28, maxWidth: 720 }}>
        <button onClick={() => setTool(null)} style={{
          display: "flex", alignItems: "center", gap: 6, border: "none", background: "transparent",
          color: T.textMuted, fontSize: 12.5, fontWeight: 600, cursor: "pointer", padding: 0, marginBottom: 14,
        }}><ArrowLeft size={13} /> All refinement tools</button>
        <SplitPanel go={go} onOperation={onOperation} />
      </div>
    );
  }
  if (tool === "merge") {
    return (
      <div style={{ padding: 28, maxWidth: 720 }}>
        <button onClick={() => setTool(null)} style={{
          display: "flex", alignItems: "center", gap: 6, border: "none", background: "transparent",
          color: T.textMuted, fontSize: 12.5, fontWeight: 600, cursor: "pointer", padding: 0, marginBottom: 14,
        }}><ArrowLeft size={13} /> All refinement tools</button>
        <MergePanel go={go} onOperation={onOperation} />
      </div>
    );
  }

  return (
    <div style={{ padding: 28, maxWidth: 780 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, color: T.text, margin: "0 0 4px" }}>What do you want to do?</h3>
      <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 20px" }}>
        Pick a refinement task. You'll come back here when you're done.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 24 }}>
        {TOOLS.map(t => (
          <button
            key={t.id}
            onClick={() => t.link ? go(t.link) : !t.disabled && setTool(t.id)}
            disabled={t.disabled}
            style={{
              display: "flex", gap: 12, alignItems: "flex-start", textAlign: "left",
              padding: "16px 18px", borderRadius: 12, border: `1px solid ${t.border}`,
              background: t.disabled ? T.bg : T.surface, cursor: t.disabled ? "not-allowed" : "pointer",
              opacity: t.disabled ? 0.55 : 1,
            }}
          >
            <div style={{
              width: 36, height: 36, borderRadius: 9, background: t.bg, color: t.color, flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}><t.Icon size={17} /></div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 3 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{t.title}</span>
                {t.disabled && <span style={{ fontSize: 10, fontWeight: 700, color: T.textMuted, background: T.border, padding: "1px 6px", borderRadius: 999 }}>SOON</span>}
              </div>
              <p style={{ margin: 0, fontSize: 12.5, color: T.textMuted, lineHeight: 1.45 }}>{t.desc}</p>
            </div>
          </button>
        ))}
      </div>

      <PageNav back={{ page: "qa", label: "QA Review" }} next={{ page: "results", label: "Results" }} go={go} />
    </div>
  );
}

/* ── Coding results for "Pourquoi aimez-vous cette boisson ?" (SABC-MAY2026) ── */
const FREQ_DATA = [
  { code: "Taste & Refreshment", count: 13, pct: 26.5 },
  { code: "Price & Value",       count: 9,  pct: 18.4 },
  { code: "Family Habit",        count: 8,  pct: 16.3 },
  { code: "Social Occasion",     count: 7,  pct: 14.3 },
  { code: "Brand Loyalty",       count: 6,  pct: 12.2 },
  { code: "Other",               count: 6,  pct: 12.2 },
];

const COOC_CODES = ["Taste", "Price", "Family", "Social", "Brand", "Other"];
const COOC_MATRIX = [
  [13, 0, 0, 2, 0, 0],
  [0,  9, 0, 0, 0, 0],
  [0,  0, 8, 1, 0, 0],
  [2,  0, 1, 7, 0, 0],
  [0,  0, 0, 0, 6, 0],
  [0,  0, 0, 0, 0, 6],
];

const CODEBOOK_DATA = [
  { code: "Taste & Refreshment", definition: "Mentions of flavor, refreshment, lightness, or how the drink feels on the palate.", inclusion: "mentions of taste, refreshment, sweetness, carbonation", exclusion: "price or brand comments; social context only", examples: "J'aime le goût rafraîchissant et léger. | It's refreshing on a hot day." },
  { code: "Price & Value",       definition: "Comments about affordability, cost, or perceived value for money.",                inclusion: "mentions of price, cost, value comparisons",       exclusion: "taste feedback; loyalty statements",         examples: "The price point feels fair for quality. | Good value compared to other brands." },
  { code: "Family Habit",        definition: "References to the drink being a long-standing family or generational habit.",       inclusion: "mentions of family tradition, upbringing, routine", exclusion: "taste or price reasoning without habit framing", examples: "C'est une habitude familiale depuis longtemps. | I always buy it because my parents did." },
  { code: "Social Occasion",     definition: "Mentions of drinking in social settings — with friends, at gatherings, or pairing with food.", inclusion: "mentions of friends, gatherings, meals, occasions", exclusion: "solo consumption; pure taste comments",          examples: "Because it pairs well with food. | Feels like a treat for social gatherings with friends." },
  { code: "Brand Loyalty",       definition: "Expressions of preference for a specific brand independent of taste or price.",      inclusion: "mentions of brand name, trust, consistency",       exclusion: "generic taste or price feedback",              examples: "Good value compared to other brands. | I always buy it because my parents did." },
  { code: "Other",               definition: "Responses that do not fit any of the predefined categories.",                        inclusion: "general or non-specific comments",                 exclusion: "any response matching a defined code",         examples: "Le goût est doux et pas trop sucré. | Easy to find in every store nearby." },
];

const CODED_ROWS = [
  { id: 1,  text: "J'aime le goût rafraîchissant et léger.",                     valid: true,  codes: ["Taste & Refreshment"] },
  { id: 2,  text: "Because it pairs well with food.",                            valid: true,  codes: ["Social Occasion"] },
  { id: 3,  text: "C'est une habitude familiale depuis longtemps.",              valid: true,  codes: ["Family Habit"] },
  { id: 4,  text: "none",                                                        valid: false, codes: [] },
  { id: 6,  text: "The price point feels fair for quality.",                     valid: true,  codes: ["Price & Value"] },
  { id: 7,  text: "Le goût est doux et pas trop sucré.",                         valid: true,  codes: ["Taste & Refreshment"] },
  { id: 9,  text: "It's refreshing on a hot day.",                               valid: true,  codes: ["Taste & Refreshment"] },
  { id: 10, text: "I always buy it because my parents did.",                     valid: true,  codes: ["Family Habit", "Brand Loyalty"] },
  { id: 11, text: "Easy to find in every store nearby.",                         valid: true,  codes: ["Other"] },
  { id: 12, text: "Feels like a treat for social gatherings with friends.",      valid: true,  codes: ["Social Occasion"] },
  { id: 15, text: "Good value compared to other brands.",                        valid: true,  codes: ["Price & Value", "Brand Loyalty"] },
  { id: 16, text: "Would buy more if prices were lower.",                        valid: true,  codes: ["Price & Value"] },
  { id: 19, text: "Nothing beats it after a long day outside.",                  valid: true,  codes: ["Taste & Refreshment"] },
  { id: 21, text: "My whole family drinks this brand.",                          valid: true,  codes: ["Family Habit"] },
  { id: 22, text: "It's the first thing I grab at a barbecue.",                  valid: true,  codes: ["Social Occasion"] },
  { id: 29, text: "Love it but the cost is a bit high.",                         valid: true,  codes: ["Price & Value"] },
  { id: 30, text: "I trust this brand more than the others.",                    valid: true,  codes: ["Brand Loyalty"] },
  { id: 37, text: "It just tastes better than the competition.",                 valid: true,  codes: ["Taste & Refreshment", "Brand Loyalty"] },
  { id: 38, text: "My grandparents drank it, now I do too.",                     valid: true,  codes: ["Family Habit"] },
  { id: 40, text: "Great for parties — everyone always asks for it.",            valid: true,  codes: ["Social Occasion"] },
];

const CODE_COLORS  = ["#3A5FFF","#10B981","#F59E0B","#EF4444","#8B5CF6","#EC4899"];
const CODE_TINTS   = ["#EEF1FF","#ECFDF5","#FEF3C7","#FEF2F2","#F5F3FF","#FDF2F8"];
const CODE_BORDERS = ["#C7D2FE","#A7F3D0","#FDE68A","#FECACA","#DDD6FE","#FBCFE8"];

/* ═══════════════════════════════════════════════════════════════════════
   QA REVIEW — human trust-building gate before results are treated as final.
   Surfaces the questions researchers actually ask about AI coding output.
   ═══════════════════════════════════════════════════════════════════════ */

const QA_DUPLICATES = 3;          // duplicate responses detected & collapsed during preprocessing
const QA_UNCODED = 0;             // valid responses that received zero codes
const QA_LOW_CONFIDENCE = [
  { id: 11, text: "Easy to find in every store nearby.", code: "Other", confidence: 54 },
  { id: 21, text: "My whole family drinks this brand.", code: "Family Habit", confidence: 61 },
  { id: 37, text: "It just tastes better than the competition.", code: "Taste & Refreshment", confidence: 58 },
];

function QAItemCard({ icon: Icon, title, status, statusLabel, children }) {
  const palette = {
    good:    { bg: "#ECFDF5", border: "#A7F3D0", color: T.accent },
    warn:    { bg: "#FEF3C7", border: "#FDE68A", color: "#B45309" },
    neutral: { bg: T.bg,      border: T.border,  color: T.textMuted },
  }[status];
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 11, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "13px 16px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: palette.bg, display: "flex", alignItems: "center", justifyContent: "center", color: palette.color, flexShrink: 0 }}>
          <Icon size={15} />
        </div>
        <span style={{ fontSize: 13.5, fontWeight: 700, color: T.text, flex: 1 }}>{title}</span>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 999,
          background: palette.bg, color: palette.color, border: `1px solid ${palette.border}`, whiteSpace: "nowrap",
        }}>{statusLabel}</span>
      </div>
      <div style={{ padding: "14px 16px" }}>{children}</div>
    </div>
  );
}

function QAReviewPage({ go }) {
  const totalValid = CODED_ROWS.filter(r => r.valid).length;
  const invalidCount = CODED_ROWS.filter(r => !r.valid).length;
  const otherCount = FREQ_DATA.find(d => d.code === "Other")?.count || 0;
  const otherPct = FREQ_DATA.find(d => d.code === "Other")?.pct || 0;
  const otherHigh = otherPct >= 15;

  // top co-occurring pair from matrix (excluding diagonal)
  let topPair = null, topVal = 0;
  COOC_MATRIX.forEach((row, ri) => row.forEach((v, ci) => {
    if (ri !== ci && v > topVal) { topVal = v; topPair = [COOC_CODES[ri], COOC_CODES[ci]]; }
  }));

  return (
    <div style={{ padding: 28, maxWidth: 920 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", borderRadius: 11,
        background: "#EEF1FF", border: "1px solid #C7D2FE", marginBottom: 22,
      }}>
        <ShieldCheck size={20} style={{ color: T.primary, flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: T.text }}>AI accelerates coding, but you approve the meaning</div>
          <div style={{ fontSize: 12.5, color: T.textMuted }}>Review these signals before results are treated as final. Nothing here blocks you — it's here so nothing surprises you later.</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>

        <QAItemCard icon={AlertCircle} title='High "Other" rate' status={otherHigh ? "warn" : "good"} statusLabel={otherHigh ? "Review suggested" : "Looks healthy"}>
          <p style={{ margin: "0 0 8px", fontSize: 13, color: T.text }}>
            <strong>{otherCount} responses ({otherPct}%)</strong> landed in "Other."
          </p>
          <p style={{ margin: 0, fontSize: 12, color: T.textMuted, lineHeight: 1.5 }}>
            {otherHigh
              ? "A rate this high usually means the codebook is missing a theme. Consider splitting Other or reviewing its examples."
              : "A healthy codebook typically keeps Other under ~15%. You're within a normal range."}
          </p>
        </QAItemCard>

        <QAItemCard icon={MessageSquareWarning} title="Low-confidence assignments" status={QA_LOW_CONFIDENCE.length > 0 ? "warn" : "good"} statusLabel={`${QA_LOW_CONFIDENCE.length} flagged`}>
          <p style={{ margin: "0 0 8px", fontSize: 13, color: T.text }}>
            <strong>{QA_LOW_CONFIDENCE.length} responses</strong> were coded below 65% model confidence.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {QA_LOW_CONFIDENCE.map(r => (
              <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, padding: "6px 8px", background: T.bg, borderRadius: 6 }}>
                <span style={{ fontWeight: 700, color: "#B45309", flexShrink: 0 }}>{r.confidence}%</span>
                <span style={{ color: T.textMuted, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>"{r.text}"</span>
                <span style={{ color: T.primary, fontWeight: 600, flexShrink: 0 }}>{r.code}</span>
              </div>
            ))}
          </div>
        </QAItemCard>

        <QAItemCard icon={Copy} title="Duplicate responses" status="neutral" statusLabel={`${QA_DUPLICATES} collapsed`}>
          <p style={{ margin: "0 0 8px", fontSize: 13, color: T.text }}>
            <strong>{QA_DUPLICATES} duplicate responses</strong> were detected and coded once during preprocessing.
          </p>
          <p style={{ margin: 0, fontSize: 12, color: T.textMuted, lineHeight: 1.5 }}>
            Their original count is preserved in frequency totals — themes won't be undercounted.
          </p>
        </QAItemCard>

        <QAItemCard icon={XCircle} title="Invalid / empty responses" status="neutral" statusLabel={`${invalidCount} excluded`}>
          <p style={{ margin: "0 0 8px", fontSize: 13, color: T.text }}>
            <strong>{invalidCount} of {CODED_ROWS.length}</strong> sampled responses were empty or non-answers (e.g. "none").
          </p>
          <p style={{ margin: 0, fontSize: 12, color: T.textMuted, lineHeight: 1.5 }}>
            Excluded from the coding denominator so percentages reflect real answers only.
          </p>
        </QAItemCard>

        <QAItemCard icon={GitMerge} title="Top co-occurring codes" status="neutral" statusLabel="Merge opportunity">
          <p style={{ margin: "0 0 8px", fontSize: 13, color: T.text }}>
            {topPair
              ? <><strong>"{topPair[0]}"</strong> and <strong>"{topPair[1]}"</strong> co-occur in {topVal} responses.</>
              : "No notable overlap detected."}
          </p>
          <button onClick={() => go("refinement")} style={{
            display: "flex", alignItems: "center", gap: 5, border: "none", background: "transparent",
            color: T.primary, fontSize: 12, fontWeight: 700, cursor: "pointer", padding: 0,
          }}><GitMerge size={12} /> Review in Refinement →</button>
        </QAItemCard>

        <QAItemCard icon={HelpCircle} title="Sample responses per code" status="good" statusLabel="Ready to validate">
          <p style={{ margin: "0 0 8px", fontSize: 13, color: T.text }}>
            Every code in the codebook has example verbatims attached.
          </p>
          <button onClick={() => go("results")} style={{
            display: "flex", alignItems: "center", gap: 5, border: "none", background: "transparent",
            color: T.primary, fontSize: 12, fontWeight: 700, cursor: "pointer", padding: 0,
          }}><BookOpen size={12} /> Open Codebook tab →</button>
        </QAItemCard>

      </div>

      {/* Uncoded responses — full width, since it's the most consequential check */}
      <QAItemCard icon={ShieldCheck} title="Uncoded responses" status={QA_UNCODED === 0 ? "good" : "warn"} statusLabel={QA_UNCODED === 0 ? "None missing" : `${QA_UNCODED} missing`}>
        <p style={{ margin: 0, fontSize: 13, color: T.text }}>
          {QA_UNCODED === 0
            ? "Every valid response received at least one code. No data is silently missing from the results."
            : `${QA_UNCODED} valid responses received no code and would be excluded from all analysis below.`}
        </p>
      </QAItemCard>

      <PageNav back={{ page: "code", label: "Code" }} next={{ page: "refinement", label: "Refinement" }} go={go} />
    </div>
  );
}


/* helper: overlay export button in top-right of a chart card */
function ChartCard({ title, icon: Icon, chartId, onExportPNG, children }) {
  return (
    <div id={chartId} style={{ position: "relative", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: 20, boxShadow: "0 1px 2px rgba(16,24,40,0.04)", marginBottom: 18 }}>
      {/* PNG export overlaid in top-right corner of the visual area */}
      <button
        onClick={() => onExportPNG?.(chartId)}
        title="Export as PNG"
        style={{
          position: "absolute", top: 12, right: 12, zIndex: 2,
          display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 6,
          border: `1px solid ${T.border}`, background: "rgba(255,255,255,0.92)",
          color: T.textMuted, fontSize: 11.5, fontWeight: 600, cursor: "pointer",
          backdropFilter: "blur(4px)", boxShadow: "0 1px 4px rgba(16,24,40,0.07)",
        }}>
        <Image size={11} /> PNG
      </button>
      <h4 style={{ margin: "0 0 16px", fontSize: 13.5, fontWeight: 700, display: "flex", alignItems: "center", gap: 7, color: T.text, paddingRight: 60 }}>
        {Icon && <Icon size={15} style={{ color: T.primary }} />} {title}
      </h4>
      {children}
    </div>
  );
}

/* ── Summary tab ── */
function SummaryTab({ exportPNG }) {
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14, marginBottom: 18 }}>
        {[["Total Responses","54"],["Valid Responses","49"],["Invalid / Empty","5"],["Codes","6"],["Multi-label","Enabled"],["Avg codes / resp.","1.08"]].map(([l,v]) => (
          <Card key={l} style={{ padding: "16px 20px" }}><Stat label={l} value={v} /></Card>
        ))}
      </div>

      <ChartCard title="Code Frequency" icon={BarChart3} chartId="chart-summary-freq" onExportPNG={exportPNG}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {FREQ_DATA.map((d, i) => (
            <div key={d.code}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 12.5, color: T.text, fontWeight: 500 }}>{d.code}</span>
                <span style={{ fontSize: 12, color: T.textMuted }}>{d.count} &nbsp;·&nbsp; {d.pct}%</span>
              </div>
              <div style={{ height: 8, borderRadius: 999, background: T.bg }}>
                <div style={{ width: `${d.pct * 4}%`, height: "100%", borderRadius: 999, background: CODE_COLORS[i % CODE_COLORS.length] }} />
              </div>
            </div>
          ))}
        </div>
      </ChartCard>
    </div>
  );
}

/* ── Frequencies tab ── */
function FrequenciesTab({ exportPNG, exportCSV, exportExcel }) {
  const max = Math.max(...FREQ_DATA.map(d => d.count));
  return (
    <div>
      <ChartCard title="Code Frequency — Bar Chart" icon={BarChart3} chartId="chart-freq-bar" onExportPNG={exportPNG}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 180, paddingBottom: 28, position: "relative" }}>
          {FREQ_DATA.map((d, i) => (
            <div key={d.code} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end" }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: CODE_COLORS[i], marginBottom: 4 }}>{d.count}</span>
              <div style={{ width: "100%", borderRadius: "5px 5px 0 0", background: CODE_COLORS[i], opacity: 0.85, height: `${(d.count / max) * 100}%`, minHeight: 4 }} />
              <span style={{ fontSize: 9.5, color: T.textMuted, marginTop: 6, textAlign: "center", lineHeight: 1.2, maxWidth: 60 }}>{d.code.split(" ").slice(0,2).join(" ")}</span>
            </div>
          ))}
        </div>
      </ChartCard>

      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: 20, marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h4 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, display: "flex", alignItems: "center", gap: 7 }}>
            <FileText size={15} style={{ color: T.primary }} /> Code Frequency — Table
          </h4>
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => exportExcel("frequencies.xlsx")} style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}><Download size={11} /> Excel</button>
            <button onClick={() => exportCSV("frequencies.csv", FREQ_DATA, ["code","count","pct"])} style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}><Download size={11} /> CSV</button>
          </div>
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: T.bg }}>
              {["Code","Count","% of Valid Responses"].map(h => <th key={h} style={th}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {FREQ_DATA.map((d, i) => (
              <tr key={d.code} style={{ borderTop: `1px solid ${T.border}` }}>
                <td style={td}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: CODE_COLORS[i], flexShrink: 0 }} />
                    {d.code}
                  </div>
                </td>
                <td style={td}>{d.count}</td>
                <td style={{ ...td, display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 80, height: 6, borderRadius: 999, background: T.bg }}>
                    <div style={{ width: `${(d.count / 49) * 100}%`, height: "100%", borderRadius: 999, background: CODE_COLORS[i] }} />
                  </div>
                  {d.pct}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Co-occurrence tab ── */
function CooccurrenceTab({ exportPNG }) {
  const maxVal = 13;
  return (
    <ChartCard title="Co-occurrence Heatmap" icon={Grid3x3} chartId="chart-cooc" onExportPNG={exportPNG}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 11.5 }}>
          <thead>
            <tr>
              <th style={{ width: 90, minWidth: 90 }} />
              {COOC_CODES.map(c => (
                <th key={c} style={{ padding: "4px 6px", fontWeight: 600, color: T.textMuted, textAlign: "center", maxWidth: 72, fontSize: 10.5 }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COOC_MATRIX.map((row, ri) => (
              <tr key={ri}>
                <td style={{ padding: "4px 8px 4px 0", fontWeight: 600, color: T.textMuted, fontSize: 10.5, whiteSpace: "nowrap" }}>{COOC_CODES[ri]}</td>
                {row.map((val, ci) => {
                  const intensity = val / maxVal;
                  return (
                    <td key={ci} title={`${COOC_CODES[ri]} × ${COOC_CODES[ci]}: ${val}`} style={{
                      width: 52, height: 52, textAlign: "center", fontWeight: 700,
                      fontSize: val === 0 ? 11 : 13, color: intensity > 0.4 ? "#fff" : T.text,
                      background: val === 0 ? T.bg : `rgba(58,95,255,${intensity * 0.9 + 0.08})`,
                      borderRadius: 6, cursor: "default",
                    }}>{val === 0 ? "—" : val}</td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p style={{ marginTop: 12, fontSize: 11.5, color: T.textMuted }}>
          Hover cells to see pair labels. Darker = higher co-occurrence.
        </p>
      </div>
    </ChartCard>
  );
}

/* ── Codebook tab ── */
function CodebookTab({ exportCSV, exportExcel }) {
  const [expanded, setExpanded]         = useState(null);
  const [inclOpen, setInclOpen]         = useState({});
  const [editingDef, setEditingDef]     = useState(null);
  const [search, setSearch]             = useState("");
  const [editVal, setEditVal]           = useState("");

  const toggleIncl = (i, e) => { e.stopPropagation(); setInclOpen(p => ({ ...p, [i]: !p[i] })); };
  const startEdit  = (i, val, e) => { e.stopPropagation(); setEditingDef(i); setEditVal(val); };

  const filtered = CODEBOOK_DATA.filter(r =>
    r.code.toLowerCase().includes(search.toLowerCase()) ||
    r.definition.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 18 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: `1px solid ${T.border}` }}>
        <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, display: "flex", alignItems: "center", gap: 8, color: T.text }}>
          <BookOpen size={16} style={{ color: T.primary }} /> Codebook
          <span style={{ fontSize: 11.5, fontWeight: 600, color: T.textMuted, background: T.bg, padding: "2px 8px", borderRadius: 999 }}>{CODEBOOK_DATA.length} codes</span>
        </h4>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => exportExcel("codebook.xlsx")} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer" }}><Download size={12} /> Excel</button>
          <button onClick={() => exportCSV("codebook.csv", CODEBOOK_DATA, ["code","definition","inclusion","exclusion","examples"])} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer" }}><Download size={12} /> CSV</button>
        </div>
      </div>

      {/* Search bar */}
      <div style={{ padding: "12px 20px", borderBottom: `1px solid ${T.border}`, background: T.bg }}>
        <div style={{ position: "relative", maxWidth: 340 }}>
          <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: T.textMuted }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search codes or definitions…"
            style={{ ...inputStyle, paddingLeft: 30, background: T.surface }} />
        </div>
      </div>

      {/* Rows */}
      <div>
        {filtered.map((row, i) => {
          const ci = CODEBOOK_DATA.indexOf(row);
          const color  = CODE_COLORS[ci % CODE_COLORS.length];
          const tint   = CODE_TINTS[ci % CODE_TINTS.length];
          const border = CODE_BORDERS[ci % CODE_BORDERS.length];
          const isExp  = expanded === ci;
          const isInclOpen = inclOpen[ci];

          return (
            <div key={row.code} style={{ borderBottom: `1px solid ${T.border}` }}>
              {/* Main row */}
              <div
                onClick={() => setExpanded(isExp ? null : ci)}
                style={{
                  display: "flex", alignItems: "flex-start", gap: 0,
                  cursor: "pointer", padding: "0",
                  background: isExp ? tint : T.surface,
                  transition: "background 0.15s",
                }}
                onMouseEnter={e => { if (!isExp) e.currentTarget.style.background = "#F9FAFB"; }}
                onMouseLeave={e => { if (!isExp) e.currentTarget.style.background = T.surface; }}
              >
                {/* Color bar */}
                <div style={{ width: 4, alignSelf: "stretch", background: color, flexShrink: 0, borderRadius: "0" }} />

                <div style={{ flex: 1, padding: "14px 16px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 700, color }}>{row.code}</span>
                      <span style={{ fontSize: 10.5, fontWeight: 700, color, background: tint, border: `1px solid ${border}`, padding: "1px 7px", borderRadius: 999 }}>
                        {CODED_ROWS.filter(r => r.codes.includes(row.code)).length} responses
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                      <button onClick={e => startEdit(ci, row.definition, e)} title="Edit definition"
                        style={{ width: 26, height: 26, borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <Edit2 size={11} />
                      </button>
                      <button onClick={e => { e.stopPropagation(); }} title="View related responses"
                        style={{ width: 26, height: 26, borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <Link2 size={11} />
                      </button>
                      <span style={{ color: T.textMuted, display: "flex", alignItems: "center" }}>
                        {isExp ? <ChevronUp size={15} /> : <ChevronRight size={15} />}
                      </span>
                    </div>
                  </div>

                  {/* Definition — inline editable */}
                  {editingDef === ci ? (
                    <div onClick={e => e.stopPropagation()} style={{ display: "flex", gap: 6, marginBottom: 6 }}>
                      <textarea value={editVal} onChange={e => setEditVal(e.target.value)} autoFocus
                        style={{ ...inputStyle, flex: 1, minHeight: 50, fontSize: 12.5 }} />
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <button onClick={() => setEditingDef(null)} style={{ padding: "4px 8px", borderRadius: 5, border: "none", background: T.primary, color: "#fff", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>Save</button>
                        <button onClick={() => setEditingDef(null)} style={{ padding: "4px 8px", borderRadius: 5, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <p style={{ margin: "0 0 8px", fontSize: 13, color: T.textMuted, lineHeight: 1.5 }}>{row.definition}</p>
                  )}

                  {/* Collapsible inclusion/exclusion toggle */}
                  <button onClick={e => toggleIncl(ci, e)} style={{
                    display: "flex", alignItems: "center", gap: 5, border: "none", background: "transparent",
                    color: T.textMuted, fontSize: 11.5, fontWeight: 600, cursor: "pointer", padding: 0, marginBottom: isInclOpen ? 8 : 0,
                  }}>
                    {isInclOpen ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    {isInclOpen ? "Hide" : "Show"} inclusion / exclusion criteria
                  </button>

                  {isInclOpen && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>
                      <div style={{ padding: "8px 10px", borderRadius: 7, background: "#F0FDF4", border: "1px solid #BBF7D0" }}>
                        <div style={{ fontSize: 10.5, fontWeight: 700, color: "#166534", marginBottom: 3, letterSpacing: "0.04em" }}>INCLUDE</div>
                        <div style={{ fontSize: 12, color: "#15803D" }}>{row.inclusion}</div>
                      </div>
                      <div style={{ padding: "8px 10px", borderRadius: 7, background: "#FEF2F2", border: "1px solid #FECACA" }}>
                        <div style={{ fontSize: 10.5, fontWeight: 700, color: "#991B1B", marginBottom: 3, letterSpacing: "0.04em" }}>EXCLUDE</div>
                        <div style={{ fontSize: 12, color: "#DC2626" }}>{row.exclusion}</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Expanded: examples */}
              {isExp && (
                <div style={{ background: tint, padding: "12px 16px 16px 20px", borderTop: `1px solid ${border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color, letterSpacing: "0.05em", marginBottom: 8 }}>EXAMPLE VERBATIMS</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                    {row.examples.split(" | ").map((ex, j) => (
                      <div key={j} style={{
                        display: "flex", gap: 10, alignItems: "flex-start",
                        padding: "9px 12px", background: T.surface, borderRadius: 8,
                        border: `1px solid ${border}`, boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                      }}>
                        <span style={{ fontSize: 14, flexShrink: 0, marginTop: -1 }}>"</span>
                        <span style={{ fontSize: 12.5, fontStyle: "italic", color: T.text, lineHeight: 1.5, flex: 1 }}>{ex}"</span>
                      </div>
                    ))}
                  </div>
                  <button onClick={e => { e.stopPropagation(); }} style={{
                    display: "flex", alignItems: "center", gap: 5, marginTop: 10,
                    border: "none", background: "transparent", color, fontSize: 12, fontWeight: 700, cursor: "pointer", padding: 0,
                  }}><Link2 size={12} /> View all {CODED_ROWS.filter(r => r.codes.includes(row.code)).length} responses in Coded Data →</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Coded Data tab ── */
/* ── Coded Data tab ── */
function CodedDataTab({ exportCSV, exportExcel }) {
  const [pageNum, setPageNum]     = useState(0);
  const [pageSize, setPageSize]   = useState(8);
  const [search, setSearch]       = useState("");
  const [filterCode, setFilterCode] = useState("All");
  const [filterValid, setFilterValid] = useState("All");
  const [hoveredRow, setHoveredRow]   = useState(null);
  const [expandedRow, setExpandedRow] = useState(null);
  const [editingRow, setEditingRow]   = useState(null);

  const filtered = CODED_ROWS.filter(r => {
    const matchText  = r.text.toLowerCase().includes(search.toLowerCase());
    const matchCode  = filterCode === "All" || r.codes.includes(filterCode);
    const matchValid = filterValid === "All" || (filterValid === "Valid" ? r.valid : !r.valid);
    return matchText && matchCode && matchValid;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage   = Math.min(pageNum, totalPages - 1);
  const pageRows   = filtered.slice(safePage * pageSize, (safePage + 1) * pageSize);

  return (
    <div>
      {/* ── Filter bar ── */}
      <div style={{
        display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center",
        padding: "10px 14px", background: T.surface, borderRadius: 10, border: `1px solid ${T.border}`,
      }}>
        <span style={{ fontSize: 11.5, fontWeight: 700, color: T.textMuted, letterSpacing: "0.05em", marginRight: 4 }}>FILTERS</span>
        <div style={{ width: 1, height: 18, background: T.border }} />
        <div style={{ position: "relative" }}>
          <Search size={12} style={{ position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)", color: T.textMuted }} />
          <input value={search} onChange={e => { setSearch(e.target.value); setPageNum(0); }}
            placeholder="Search responses…"
            style={{ ...inputStyle, paddingLeft: 28, width: 190, height: 32, fontSize: 12.5 }} />
        </div>
        <select value={filterCode} onChange={e => { setFilterCode(e.target.value); setPageNum(0); }}
          style={{ ...inputStyle, width: "auto", height: 32, fontSize: 12.5, paddingTop: 0, paddingBottom: 0 }}>
          <option value="All">All codes</option>
          {FREQ_DATA.map(d => <option key={d.code} value={d.code}>{d.code}</option>)}
        </select>
        <select value={filterValid} onChange={e => { setFilterValid(e.target.value); setPageNum(0); }}
          style={{ ...inputStyle, width: "auto", height: 32, fontSize: 12.5, paddingTop: 0, paddingBottom: 0 }}>
          <option value="All">All rows</option>
          <option value="Valid">Valid only</option>
          <option value="Invalid">Invalid only</option>
        </select>
        <span style={{ fontSize: 12, color: T.textMuted }}>
          {filtered.length} row{filtered.length !== 1 ? "s" : ""}
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: T.textMuted }}>Per page:</span>
          <select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPageNum(0); }}
            style={{ ...inputStyle, width: 64, height: 30, fontSize: 12, paddingTop: 0, paddingBottom: 0 }}>
            {[5,8,15,25].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
          <button onClick={() => exportExcel("coded_responses.xlsx")} style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}><Download size={11} /> Excel</button>
          <button onClick={() => exportCSV("coded_responses.csv", filtered.map(r=>({ID:r.id,Response:r.text,Valid:r.valid,Codes:r.codes.join(";")})), ["ID","Response","Valid","Codes"])} style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}><Download size={11} /> CSV</button>
        </div>
      </div>

      {/* ── Table ── */}
      <div style={{ border: `1px solid ${T.border}`, borderRadius: 10, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: T.bg, position: "sticky", top: 0, zIndex: 1 }}>
              <th style={{ ...th, width: 42 }}>ID</th>
              <th style={th}>Response</th>
              <th style={th}>Code(s)</th>
              <th style={{ ...th, width: 80 }}>Status</th>
              <th style={{ ...th, width: 100 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r, i) => {
              const isHov = hoveredRow === r.id;
              const isExp = expandedRow === r.id;
              return (
                <React.Fragment key={r.id}>
                  <tr
                    onMouseEnter={() => setHoveredRow(r.id)}
                    onMouseLeave={() => setHoveredRow(null)}
                    style={{
                      borderTop: `1px solid ${T.border}`,
                      background: isHov ? "#F0F4FF" : i % 2 === 1 ? "#FAFAFA" : T.surface,
                      transition: "background 0.1s",
                      cursor: "pointer",
                    }}
                    onClick={() => setExpandedRow(isExp ? null : r.id)}
                  >
                    <td style={{ ...td, color: T.textMuted, fontVariantNumeric: "tabular-nums" }}>{r.id}</td>
                    <td style={{ ...td, maxWidth: 320, lineHeight: 1.5 }}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
                        <span style={{ flexShrink: 0, marginTop: 2 }}>
                          {r.valid
                            ? <CheckCircle2 size={13} color={T.accent} />
                            : <XCircle size={13} color="#EF4444" />}
                        </span>
                        <span style={{ color: r.valid ? T.text : T.textMuted, fontStyle: r.valid ? "normal" : "italic" }}>
                          {r.text}
                        </span>
                      </div>
                    </td>
                    <td style={{ ...td }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {r.codes.length === 0
                          ? <span style={{ color: T.textMuted, fontSize: 11.5 }}>—</span>
                          : r.codes.map(c => {
                              const ci = FREQ_DATA.findIndex(d => d.code === c);
                              return (
                                <span key={c} style={{
                                  display: "inline-flex", alignItems: "center", gap: 4,
                                  fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 999,
                                  background: CODE_TINTS[ci % CODE_TINTS.length],
                                  color: CODE_COLORS[ci % CODE_COLORS.length],
                                  border: `1px solid ${CODE_BORDERS[ci % CODE_BORDERS.length]}`,
                                  whiteSpace: "nowrap",
                                }}>
                                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: CODE_COLORS[ci % CODE_COLORS.length], flexShrink: 0 }} />
                                  {c}
                                </span>
                              );
                            })
                        }
                      </div>
                    </td>
                    <td style={{ ...td }}>
                      <span style={{
                        display: "inline-flex", alignItems: "center", gap: 4,
                        fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 999,
                        background: r.valid ? "#ECFDF5" : "#FEF2F2",
                        color: r.valid ? T.accent : "#EF4444",
                        border: `1px solid ${r.valid ? "#A7F3D0" : "#FECACA"}`,
                      }}>
                        {r.valid ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                        {r.valid ? "Valid" : "Invalid"}
                      </span>
                    </td>
                    <td style={{ ...td }} onClick={e => e.stopPropagation()}>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button title="Edit codes" style={{ width: 26, height: 26, borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Edit2 size={11} />
                        </button>
                        <button title="View full response" onClick={() => setExpandedRow(isExp ? null : r.id)} style={{ width: 26, height: 26, borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Eye size={11} />
                        </button>
                        <button title={r.valid ? "Mark invalid" : "Mark valid"} style={{ width: 26, height: 26, borderRadius: 6, border: `1px solid ${T.border}`, background: T.surface, color: r.valid ? "#EF4444" : T.accent, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {r.valid ? <XCircle size={11} /> : <CheckCircle2 size={11} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {isExp && (
                    <tr style={{ background: "#F0F4FF", borderTop: `1px solid ${T.border}` }}>
                      <td colSpan={5} style={{ padding: "12px 16px 14px 42px" }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 6, letterSpacing: "0.04em" }}>FULL RESPONSE</div>
                        <p style={{ margin: 0, fontSize: 13.5, color: T.text, lineHeight: 1.6, fontStyle: "italic" }}>"{r.text}"</p>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 14 }}>
        <span style={{ fontSize: 12.5, color: T.textMuted }}>
          Showing {safePage * pageSize + 1}–{Math.min((safePage + 1) * pageSize, filtered.length)} of {filtered.length}
        </span>
        <div style={{ display: "flex", gap: 5 }}>
          <button onClick={() => setPageNum(p => Math.max(0, p - 1))} disabled={safePage === 0} style={{
            padding: "6px 12px", borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface,
            color: safePage === 0 ? T.border : T.text, cursor: safePage === 0 ? "not-allowed" : "pointer", fontSize: 13,
          }}>← Prev</button>
          {Array.from({ length: totalPages }).map((_, pi) => (
            <button key={pi} onClick={() => setPageNum(pi)} style={{
              width: 30, height: 30, borderRadius: 7, border: `1px solid ${pi === safePage ? T.primary : T.border}`,
              background: pi === safePage ? T.primary : T.surface, color: pi === safePage ? "#fff" : T.text,
              fontSize: 13, cursor: "pointer", fontWeight: pi === safePage ? 700 : 400,
            }}>{pi + 1}</button>
          ))}
          <button onClick={() => setPageNum(p => Math.min(totalPages - 1, p + 1))} disabled={safePage >= totalPages - 1} style={{
            padding: "6px 12px", borderRadius: 7, border: `1px solid ${T.border}`, background: T.surface,
            color: safePage >= totalPages - 1 ? T.border : T.text, cursor: safePage >= totalPages - 1 ? "not-allowed" : "pointer", fontSize: 13,
          }}>Next →</button>
        </div>
      </div>
    </div>
  );
}


function ResultsPage({ go, operations, onUndo }) {
  const TABS = [
    { id: "summary",    label: "Summary",       Icon: BarChart3 },
    { id: "freq",       label: "Frequencies",   Icon: BarChart3 },
    { id: "cooc",       label: "Co-occurrence", Icon: Grid3x3 },
    { id: "codebook",   label: "Codebook",      Icon: BookOpen },
    { id: "coded",      label: "Coded Data",    Icon: FileText },
  ];
  const [activeTab, setActiveTab] = useState("summary");

  const exportCSV = (filename, rows, headers) => {
    const csv = [headers.join(","), ...rows.map(r => headers.map(h => `"${r[h] ?? ''}"`).join(","))].join("\n");
    const a = document.createElement("a"); a.href = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
    a.download = filename; a.click();
  };

  const exportExcel = (filename) => {
    // In prototype: export as TSV (simulates Excel; real impl uses SheetJS)
    const rows = CODED_ROWS.map(r => ({ ID: r.id, Response: r.text, Valid: r.valid, Codes: r.codes.join("; ") }));
    const tsv = ["ID\tResponse\tValid\tCodes", ...rows.map(r => `${r.ID}\t${r.Response}\t${r.Valid}\t${r.Codes}`)].join("\n");
    const a = document.createElement("a"); a.href = "data:application/vnd.ms-excel;charset=utf-8," + encodeURIComponent(tsv);
    a.download = filename; a.click();
  };

  const exportPNG = (chartId) => {
    const el = document.getElementById(chartId);
    if (!el) { alert("PNG export: capture library not loaded in prototype."); return; }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Undo banners for split/merge operations */}
      {operations && operations.length > 0 && (
        <div style={{ flexShrink: 0, background: "#FFFBEB", borderBottom: `1px solid #FDE68A`, padding: "0 28px" }}>
          {operations.map((op, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0", borderBottom: i < operations.length - 1 ? `1px solid #FDE68A` : "none" }}>
              <span style={{ fontSize: 12, color: "#92400E", flex: 1 }}>
                {op.type === "split"
                  ? `Split applied: "${op.codes.join('", "')}" → ${op.subCodes.join(", ")}`
                  : `Merge applied: "${op.codes.join('" + "')}" → "${op.mergedName}"`}
              </span>
              <button onClick={() => onUndo(i)} style={{
                display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 6,
                border: "1px solid #F59E0B", background: "#fff", color: "#B45309",
                fontSize: 11.5, fontWeight: 600, cursor: "pointer",
              }}><RotateCcw size={11} /> Undo</button>
            </div>
          ))}
        </div>
      )}

      {/* Tab bar */}
      <div style={{
        display: "flex", gap: 0, borderBottom: `1px solid ${T.border}`,
        background: T.surface, padding: "0 28px", flexShrink: 0,
      }}>
        {TABS.map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setActiveTab(id)} style={{
            display: "flex", alignItems: "center", gap: 6, padding: "13px 18px",
            border: "none", borderBottom: activeTab === id ? `2px solid ${T.primary}` : "2px solid transparent",
            background: "transparent", fontFamily: "inherit",
            color: activeTab === id ? T.primary : T.textMuted,
            fontSize: 13.5, fontWeight: activeTab === id ? 700 : 500, cursor: "pointer",
            marginBottom: -1,
          }}>
            <Icon size={14} /> {label}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, paddingRight: 4 }}>
          <button onClick={() => exportExcel("coded_data.xlsx")} style={{
            display: "flex", alignItems: "center", gap: 6, padding: "7px 12px", borderRadius: 7,
            border: `1px solid ${T.border}`, background: T.surface, color: T.text,
            fontSize: 12, fontWeight: 600, cursor: "pointer",
          }}><Download size={12} /> Excel</button>
          <button onClick={() => exportCSV("coded_data.csv", CODED_ROWS.map(r=>({ID:r.id,Response:r.text,Valid:r.valid,Codes:r.codes.join(";")})), ["ID","Response","Valid","Codes"])} style={{
            display: "flex", alignItems: "center", gap: 6, padding: "7px 12px", borderRadius: 7,
            border: `1px solid ${T.border}`, background: T.surface, color: T.text,
            fontSize: 12, fontWeight: 600, cursor: "pointer",
          }}><Download size={12} /> CSV</button>
        </div>
      </div>

      {/* Tab body */}
      <div style={{ flex: 1, overflow: "auto", padding: 28, maxWidth: 1060 }}>
        {activeTab === "summary"  && <SummaryTab exportPNG={exportPNG} />}
        {activeTab === "freq"     && <FrequenciesTab exportPNG={exportPNG} exportCSV={exportCSV} exportExcel={exportExcel} />}
        {activeTab === "cooc"     && <CooccurrenceTab exportPNG={exportPNG} />}
        {activeTab === "codebook" && <CodebookTab exportCSV={exportCSV} exportExcel={exportExcel} />}
        {activeTab === "coded"    && <CodedDataTab exportCSV={exportCSV} exportExcel={exportExcel} />}
        <PageNav back={{ page: "refinement", label: "Refinement" }} finish go={go} />
      </div>
    </div>
  );
}

/* ---------- root ---------- */

export default function App() {
  const [page, setPage] = useState("projects");
  const [operations, setOperations] = useState([]); // split/merge history for undo

  const go = (p) => { setPage(p); window.scrollTo?.(0, 0); };

  const handleOperation = (op) => setOperations(prev => [op, ...prev]);
  const handleUndo = (idx) => setOperations(prev => prev.filter((_, i) => i !== idx));

  const renderPage = () => {
    switch (page) {
      case "projects":       return <ProjectsPage go={go} />;
      case "create-project": return <CreateProjectPage go={go} />;
      case "context":        return <ContextPage go={go} />;
      case "add-question":   return <AddQuestionPage go={go} />;
      case "upload":         return <UploadPage go={go} />;
      case "preprocess":     return <PreprocessPage go={go} />;
      case "code":           return <CodePage go={go} onCodingComplete={() => {}} />;
      case "qa":             return <QAReviewPage go={go} />;
      case "refinement":     return <RefinementPage go={go} onOperation={handleOperation} />;
      case "results":        return <ResultsPage go={go} operations={operations} onUndo={handleUndo} />;
      case "admin":
      case "settings":
        return (
          <div style={{ padding: 28 }}>
            <Card style={{ maxWidth: 500 }}>
              <p style={{ color: T.textMuted, fontSize: 14, margin: 0 }}>
                {page === "admin" ? "Admin setup" : "Settings"} — out of scope for this prototype.
              </p>
              <div style={{ marginTop: 14 }}><Btn onClick={() => go("projects")}>Back to Projects</Btn></div>
            </Card>
          </div>
        );
      default: return null;
    }
  };

  return (
    <div style={{
      fontFamily: "Inter, -apple-system, sans-serif", display: "flex", height: "100vh",
      background: T.bg, color: T.text,
    }}>
      <Sidebar page={page} go={go} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <TopBar page={page} />
        <div style={{ flex: 1, overflow: "auto" }}>{renderPage()}</div>
      </div>
    </div>
  );
}
