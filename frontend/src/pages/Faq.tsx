import type { FC } from 'react';
import { Link } from 'react-router-dom';
import PageShell from '../components/PageShell';
import Panel from '../components/ui/Panel';

const TIERS = [
  {
    name: 'Novice',
    rep: '0+',
    summary: 'Short teasers and chapters. A couple of posts per day. You can vote from day one.',
  },
  {
    name: 'Apprentice',
    rep: '50+',
    summary: 'A bit more room to write, one more post each day, and looser spacing between your parts.',
  },
  {
    name: 'Storyteller',
    rep: '150+',
    summary: 'Longer scenes, more daily posts, and less waiting between your own parts.',
  },
  {
    name: 'Master',
    rep: '300+',
    summary: 'Generous length and posting limits. You may continue your own threads freely.',
  },
  {
    name: 'Legend',
    rep: '500+',
    summary: 'The fullest canvas — longest chapters and the highest daily allowance.',
  },
] as const;

/** Plain-language guide to tiers, limits, and how stories earn trust. */
const Faq: FC = () => (
  <PageShell>
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-10">
      <header>
        <p className="text-sm text-muted mb-2">
          <Link to="/" className="text-accent hover:text-accent-hover">
            ← Back to stories
          </Link>
        </p>
        <h1 className="text-2xl font-semibold text-text">How writing works here</h1>
        <p className="mt-3 font-serif text-lg leading-relaxed text-muted">
          Everyone starts as a Novice. As readers appreciate your work, you earn
          reputation — and with it, more room to write and shape the archive.
        </p>
      </header>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          Author tiers
        </h2>
        <Panel className="overflow-hidden divide-y divide-border">
          {TIERS.map((tier) => (
            <div key={tier.name} className="px-6 py-4">
              <div className="flex items-baseline justify-between gap-4">
                <h3 className="font-semibold text-text">{tier.name}</h3>
                <span className="text-sm text-muted tabular-nums shrink-0">
                  Reputation {tier.rep}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted leading-relaxed">{tier.summary}</p>
            </div>
          ))}
        </Panel>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          Growing your reputation
        </h2>
        <Panel className="p-6">
          <p className="font-serif text-lg leading-relaxed text-text">
            Reputation rises when people upvote the parts you write. A few thoughtful
            votes from trusted authors weigh more than a rush of empty praise. Writing
            many parts back-to-back in a short time earns less credit — good stories
            breathe.
          </p>
        </Panel>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          Voting
        </h2>
        <Panel className="p-6">
          <p className="font-serif text-lg leading-relaxed text-text">
            Everyone can upvote and downvote from the start — including Novices — so
            good writing can earn reputation right away. Higher tiers unlock longer
            chapters, more daily posts, and freer spacing, not the right to vote.
          </p>
        </Panel>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          Daily posts and length
        </h2>
        <Panel className="p-6 space-y-4">
          <p className="font-serif text-lg leading-relaxed text-text">
            Each tier caps how long your teaser and chapter may be, and how many parts
            you may publish in a day. Counters under the writing fields show where you
            stand; if you go over, they turn red and publishing waits until you trim.
          </p>
          <p className="font-serif text-lg leading-relaxed text-text">
            When you have used today&apos;s allowance, the writing boxes stay closed —
            so you never draft a scene only to learn you cannot publish it.
          </p>
        </Panel>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          Taking turns on a thread
        </h2>
        <Panel className="p-6">
          <p className="font-serif text-lg leading-relaxed text-text">
            On early tiers, a few other authors must write between your parts on the
            same path. That keeps one person from filling an entire branch alone.
            Higher tiers relax or remove that spacing.
          </p>
        </Panel>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          How stories rise
        </h2>
        <Panel className="p-6">
          <p className="font-serif text-lg leading-relaxed text-text">
            The score you see is a simple up-minus-down tally. Behind the scenes, the
            archive also listens to confidence and trust: popular branches by respected
            authors climb more steadily than brand-new parts with a single vote. You
            do not need the math — write well, and the shelves remember.
          </p>
        </Panel>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
          Reports and moderation
        </h2>
        <Panel className="p-6 space-y-4">
          <p className="font-serif text-lg leading-relaxed text-text">
            If a part feels harmful or spammy, use Report. Enough independent reports
            hide it from the public shelves until a moderator reviews it. Parts that
            fall far below the community score, or accounts that post too fast, may
            also be quarantined automatically.
          </p>
          <p className="font-serif text-lg leading-relaxed text-text">
            Moderators can allow a part back, permanently hide it (children stay, but
            the part itself remains invisible), or block an account. Rate limits on
            login and writing slow down automated abuse without replacing your daily
            posting quota.
          </p>
          <p className="font-serif text-lg leading-relaxed text-text">
            Copy-paste duplicates are rejected. Web links are not allowed in story
            parts. Obviously spammy wording may be held for moderator review
            automatically. Sudden bursts of posting or voting on an older account
            can also freeze the account for review — a sign it may have been taken
            over. Moderators may also issue a temporary warning that pauses writing
            for a day while you take the feedback on board. The moderator desk
            supports bulk cleanup and flags unusual voting patterns for review.
          </p>
        </Panel>
      </section>
    </main>
  </PageShell>
);

export default Faq;
