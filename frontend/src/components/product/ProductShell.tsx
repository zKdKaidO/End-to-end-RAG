import { type ReactNode, useEffect, useState } from "react";
import { FileText, LogOut, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { ZkdWordmark } from "./ZkdWordmark";
import type { AuthUser, ChatSession } from "../../types";
import "./ProductShell.css";

type LegacySidebarConfig = {
  user: AuthUser;
  sessions?: ChatSession[];
  activeSessionId?: string | null;
  hasOlderSessions?: boolean;
  onSelectSession?: (sessionId: string) => void;
  onCreateSession?: () => void | Promise<void>;
  onRenameSession?: (session: ChatSession) => void | Promise<void>;
  onDeleteSession?: (session: ChatSession) => void | Promise<void>;
  onLoadOlderSessions?: () => void;
  onLogout: () => void | Promise<void>;
};

type ProductShellProps = {
  user?: AuthUser;
  onLogout?: () => void | Promise<void>;
  sidebar?: LegacySidebarConfig;
  rightOpen?: boolean;
  onCloseRight?: () => void;
  rightPanel?: ReactNode;
  children: ReactNode;
};

export function ProductShell({
  user,
  onLogout,
  sidebar,
  rightOpen = false,
  rightPanel = null,
  children,
}: ProductShellProps) {
  const navigate = useNavigate();

  const resolvedUser = user ?? sidebar?.user;
  const resolvedLogout = onLogout ?? sidebar?.onLogout;

  const [collapsed, setCollapsed] = useState(() => {
    return window.localStorage.getItem("zkd-product-sidebar-collapsed") === "1";
  });

  useEffect(() => {
    window.localStorage.setItem(
      "zkd-product-sidebar-collapsed",
      collapsed ? "1" : "0",
    );
  }, [collapsed]);

  if (!resolvedUser) {
    throw new Error("ProductShell requires a user.");
  }

  const logout = () => {
    if (resolvedLogout) {
      void resolvedLogout();
    }
  };

  return (
    <div className={`zkd-product-shell ${collapsed ? "is-collapsed" : ""} ${rightOpen ? "has-right-panel" : ""}`}>
      <aside className="zkd-product-sidebar">
        <div className={`zkd-product-sidebar-top ${collapsed ? "is-collapsed" : ""}`}>
          {!collapsed ? (
            <button
              type="button"
              className="zkd-product-brand"
              aria-label="Go to zKd AI"
              onClick={() => navigate("/ask")}
            >
              <ZkdWordmark />
            </button>
          ) : null}

          <button
            type="button"
            className="zkd-product-collapse"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>

        <button
          type="button"
          className="zkd-product-new"
          title="New inquiry"
          onClick={() => navigate("/ask")}
        >
          <Plus size={17} strokeWidth={1.8} />
          {!collapsed ? <span>New</span> : null}
        </button>

        <nav className="zkd-product-nav" aria-label="Workspace navigation">
          <NavLink
            to="/ask"
            title="Ask"
            className={({ isActive }) => `zkd-product-nav-item ${isActive ? "is-active" : ""}`}
          >
            <MessageSquare size={17} strokeWidth={1.8} />
            {!collapsed ? <span>Ask</span> : null}
          </NavLink>

          <NavLink
            to="/documents"
            title="Documents"
            className={({ isActive }) => `zkd-product-nav-item ${isActive ? "is-active" : ""}`}
          >
            <FileText size={17} strokeWidth={1.8} />
            {!collapsed ? <span>Documents</span> : null}
          </NavLink>
        </nav>

        <div className="zkd-product-sidebar-spacer" />

        <div className={`zkd-product-user ${collapsed ? "is-collapsed" : ""}`}>
          <div className="zkd-product-avatar">
            {resolvedUser.email.slice(0, 1).toUpperCase()}
          </div>

          {!collapsed ? (
            <div className="zkd-product-user-copy">
              <strong title={resolvedUser.email}>
                {resolvedUser.email}
              </strong>
              <span>{resolvedUser.role}</span>
            </div>
          ) : null}

          <button
            type="button"
            className="zkd-product-logout"
            aria-label="Sign out"
            title="Sign out"
            onClick={logout}
          >
            <LogOut size={15} />
          </button>
        </div>
      </aside>

      <main className="zkd-product-content">
        {children}
      </main>

      {rightOpen && rightPanel ? (
        <aside className="zkd-product-right-panel">
          {rightPanel}
        </aside>
      ) : null}
    </div>
  );
}