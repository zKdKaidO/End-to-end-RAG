import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type LegalPageProps = {
  kind: "privacy" | "terms";
};

function PublicLegalLayout({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: ReactNode;
}) {
  return (
    <main className="public-legal-page">
      <header className="public-legal-header">
        <Link className="public-legal-brand" to="/" aria-label="ZKD home">
          <span aria-hidden="true">Z</span>
          <strong>ZKD</strong>
        </Link>
        <nav aria-label="Public legal navigation">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
        </nav>
      </header>

      <article className="public-legal-content">
        <p className="public-legal-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="public-legal-updated">Last updated: September 6, 2026</p>
        {children}
      </article>

      <footer className="public-legal-footer">
        <span>© {new Date().getFullYear()} ZKD</span>
        <a href="mailto:phamnhatnamthsg@gmail.com">Privacy and support contact</a>
      </footer>
    </main>
  );
}

function PrivacyPolicy() {
  return (
    <PublicLegalLayout eyebrow="ZKD privacy" title="Privacy Policy">
      <section>
        <h2>What this policy covers</h2>
        <p>This policy describes how ZKD handles account and service information. It is product information for an early public software product, not a substitute for professional legal advice.</p>
      </section>

      <section>
        <h2>Information we collect</h2>
        <p>ZKD may process account identity, server-side session records, device metadata, pairing and control metadata, device presence, and local-document manifest metadata needed to operate the service.</p>
        <p>When you choose Google sign-in, ZKD uses the immutable Google subject identifier (<code>sub</code>) and your verified email address to authenticate and link your ZKD account. Google&apos;s standard OpenID Connect profile scope may provide basic profile information during sign-in; the current control plane persists the identity link and email used for the account.</p>
      </section>

      <section>
        <h2>How Google information is used</h2>
        <p>Google OAuth is used only for authentication. ZKD does not request Gmail, Drive, Calendar, Contacts, or other Google API data.</p>
        <p>ZKD does not persist Google access tokens, refresh tokens, ID tokens, or OAuth authorization codes. After authentication, ZKD creates its own opaque, server-side session.</p>
      </section>

      <section>
        <h2>Local-first document processing</h2>
        <p>Uploaded PDF and document contents, extracted document text, chunks, embeddings, retrieved context, prompts, and generated document answers remain in local ZKD Compute. They are not stored by the Cloudflare metadata control plane.</p>
        <p>The cloud control plane is limited to account and operational metadata, including identity, sessions, device and pairing/control metadata, presence, and local-document manifest metadata. It is not a storage service for your source documents or generated research content.</p>
      </section>

      <section>
        <h2>Retention, security, and your choices</h2>
        <p>Session records expire according to the configured session lifetime. Account, identity-link, device, and operational metadata are retained while needed to provide, secure, and support the service, subject to applicable operational or legal requirements.</p>
        <p>We use reasonable technical measures intended to protect the service, including secure transport and secure, HTTP-only session cookies. No online service can guarantee absolute security.</p>
        <p>For privacy questions, access, correction, or deletion requests, contact <a href="mailto:phamnhatnamthsg@gmail.com">phamnhatnamthsg@gmail.com</a>. We will review requests in light of the information we hold and applicable obligations.</p>
      </section>

      <section>
        <h2>Policy updates</h2>
        <p>We may update this policy as ZKD develops. Material changes will be reflected on this page with an updated date.</p>
      </section>
    </PublicLegalLayout>
  );
}

function TermsOfService() {
  return (
    <PublicLegalLayout eyebrow="ZKD product terms" title="Terms of Service">
      <section>
        <h2>Using ZKD</h2>
        <p>ZKD is an early public software product for local-first document research and related device coordination. You may use it only in accordance with these terms and applicable law.</p>
      </section>

      <section>
        <h2>Your content and responsibilities</h2>
        <p>You are responsible for the documents you process, the permissions you have to use them, and the decisions you make using ZKD. Do not use the service to process content you are not authorized to handle.</p>
        <p>ZKD may generate research-oriented output from information available to your local Compute device. That output is not legal, financial, medical, or other professional advice, and should be reviewed independently before it is relied upon.</p>
      </section>

      <section>
        <h2>Accounts and Google sign-in</h2>
        <p>You are responsible for activity performed through your ZKD account and connected device. Google sign-in is an optional authentication method; use of it is also subject to Google&apos;s applicable terms and policies.</p>
      </section>

      <section>
        <h2>Service availability</h2>
        <p>ZKD is provided on an as-available basis while the product is evolving. Features may change, be limited, or be discontinued. We do not promise uninterrupted availability or a particular research outcome.</p>
      </section>

      <section>
        <h2>Privacy, feedback, and contact</h2>
        <p>Our handling of account and operational information is described in the <Link to="/privacy">Privacy Policy</Link>. For account, privacy, support, or deletion requests, contact <a href="mailto:phamnhatnamthsg@gmail.com">phamnhatnamthsg@gmail.com</a>.</p>
      </section>

      <section>
        <h2>Updates to these terms</h2>
        <p>We may update these terms as the product changes. Continued use after an update means you should review the revised terms. If you do not agree, stop using the service.</p>
      </section>
    </PublicLegalLayout>
  );
}

export function PublicLegalPage({ kind }: LegalPageProps) {
  return kind === "privacy" ? <PrivacyPolicy /> : <TermsOfService />;
}
