import { useEffect, useState } from "react";
import { ArrowLeft, FileText, GitBranch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { getRunSnapshot, type RunSnapshot, type CanonicalEntity } from "@/lib/api";

interface RunDetailViewProps {
  runId: string;
  onBack: () => void;
}

interface TelemetryRecord {
  query: string;
  round_num: number;
  strategy: string;
  results_total: number;
  results_qualified: number;
  avg_score: number;
  reject_reasons: string[];
}

interface SourceAttemptRecord {
  base_url: string;
  strategy: string;
  source_class?: string | null;
  result_count: number;
  succeeded: boolean;
  error?: string | null;
}

interface AuditReport {
  metrics: Record<string, number>;
  notes: string[];
}

function truncate(text: string, max = 24): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function EntityCard({ entity, snapshot }: { entity: CanonicalEntity; snapshot: RunSnapshot }) {
  const [expanded, setExpanded] = useState(false);
  const chain = snapshot.evidence_chains.find((c) => c.entity_id === entity.entity_id);

  return (
    <li className="glass-1 border border-border/30 rounded-lg p-3 space-y-1.5 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-2 text-left"
      >
        <span className="type-body font-medium">{entity.title}</span>
        <Badge variant="outline">{entity.confidence.toFixed(2)}</Badge>
      </button>
      {entity.summary && <p className="type-caption text-muted-foreground">{entity.summary}</p>}

      {expanded && (
        <div className="pt-2 border-t border-border/20 space-y-2">
          {chain ? (
            <>
              {(chain.first_captured_at || chain.last_captured_at) && (
                <p className="type-caption text-muted-foreground">
                  {chain.first_captured_at ?? "?"} → {chain.last_captured_at ?? "?"}
                </p>
              )}
              <ul className="space-y-1.5">
                {chain.links.map((link) => (
                  <li key={link.evidence_id} className="text-xs-minus border-l-2 border-border/40 pl-2 space-y-0.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {link.source_name && <span className="font-medium">{link.source_name}</span>}
                      {link.title && <span className="text-muted-foreground">{link.title}</span>}
                    </div>
                    {link.snippet && <p className="text-muted-foreground">{link.snippet}</p>}
                    {link.captured_at && (
                      <span className="text-muted-foreground/70">{link.captured_at}</span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="type-caption text-muted-foreground/50">no evidence chain for this entity</p>
          )}
        </div>
      )}
    </li>
  );
}

function EntitiesTab({ snapshot }: { snapshot: RunSnapshot }) {
  if (snapshot.entities.length === 0) {
    return <EmptyState icon={FileText} label="no entities in this run" />;
  }
  return (
    <ul className="space-y-2">
      {snapshot.entities.map((entity) => (
        <EntityCard key={entity.entity_id} entity={entity} snapshot={snapshot} />
      ))}
    </ul>
  );
}

function QueriesTab({ snapshot }: { snapshot: RunSnapshot }) {
  const telemetry = snapshot.telemetry as unknown as TelemetryRecord[];
  if (telemetry.length === 0) {
    return <EmptyState icon={FileText} label="no query telemetry in this run" />;
  }
  const byRound = new Map<number, TelemetryRecord[]>();
  for (const record of telemetry) {
    const list = byRound.get(record.round_num) ?? [];
    list.push(record);
    byRound.set(record.round_num, list);
  }
  const rounds = [...byRound.keys()].sort((a, b) => a - b);

  return (
    <div className="space-y-4">
      {rounds.map((round) => (
        <div key={round} className="space-y-1.5">
          <span className="type-label text-muted-foreground">round {round}</span>
          <ul className="space-y-1.5">
            {byRound.get(round)!.map((record, i) => (
              <li key={i} className="glass-1 border border-border/30 rounded-lg p-2.5 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs-minus">{record.query}</span>
                  <Badge variant="outline">{record.strategy}</Badge>
                </div>
                <div className="flex items-center gap-2 flex-wrap type-caption text-muted-foreground">
                  <span>
                    {record.results_qualified} / {record.results_total} qualified
                  </span>
                  <span>avg score {record.avg_score.toFixed(2)}</span>
                </div>
                {record.reject_reasons.length > 0 && (
                  <div className="flex items-center gap-1 flex-wrap">
                    {record.reject_reasons.map((reason, j) => (
                      <Badge key={j} variant="secondary">
                        {reason}
                      </Badge>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function HyperedgesTab({ snapshot }: { snapshot: RunSnapshot }) {
  if (snapshot.hyperedges.length === 0) {
    return <EmptyState icon={GitBranch} label="no hyperedges in this run" />;
  }
  return (
    <ul className="space-y-2">
      {snapshot.hyperedges.map((edge) => (
        <li key={edge.hyperedge_id} className="glass-1 border border-border/30 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline">{edge.hyperedge_type}</Badge>
            <span className="type-caption text-muted-foreground">confidence {edge.confidence.toFixed(2)}</span>
          </div>
          {edge.summary && <p className="type-body">{edge.summary}</p>}
          {edge.members.length > 0 && (
            <table className="w-full text-xs-minus border-collapse">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border/20">
                  <th className="py-1 pr-2 font-medium">role</th>
                  <th className="py-1 pr-2 font-medium">kind</th>
                  <th className="py-1 pr-2 font-medium">member</th>
                  <th className="py-1 pr-2 font-medium text-right">weight</th>
                </tr>
              </thead>
              <tbody>
                {edge.members.map((member, i) => (
                  <tr key={i} className="border-b border-border/10">
                    <td className="py-1 pr-2">{member.role}</td>
                    <td className="py-1 pr-2">{member.member_kind}</td>
                    <td className="py-1 pr-2">{truncate(member.member_id)}</td>
                    <td className="py-1 pr-2 text-right">{member.weight.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </li>
      ))}
    </ul>
  );
}

function SourcesTab({ snapshot }: { snapshot: RunSnapshot }) {
  const attempts = snapshot.source_attempts as unknown as SourceAttemptRecord[];
  if (attempts.length === 0) {
    return <EmptyState icon={FileText} label="no source attempts in this run" />;
  }
  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="text-left type-caption text-muted-foreground border-b border-border/40">
          <th className="py-1.5 pr-3 font-medium">base url</th>
          <th className="py-1.5 pr-3 font-medium">strategy</th>
          <th className="py-1.5 pr-3 font-medium">class</th>
          <th className="py-1.5 pr-3 font-medium">status</th>
          <th className="py-1.5 pr-3 font-medium text-right">results</th>
          <th className="py-1.5 pr-3 font-medium">error</th>
        </tr>
      </thead>
      <tbody>
        {attempts.map((attempt, i) => (
          <tr key={i} className="border-b border-border/20">
            <td className="py-1.5 pr-3 truncate max-w-[220px]">{attempt.base_url}</td>
            <td className="py-1.5 pr-3">{attempt.strategy}</td>
            <td className="py-1.5 pr-3">{attempt.source_class ?? "—"}</td>
            <td className="py-1.5 pr-3">
              <span
                className={`inline-block w-1.5 h-1.5 rounded-full ${attempt.succeeded ? "bg-success" : "bg-destructive"}`}
              />
            </td>
            <td className="py-1.5 pr-3 text-right">{attempt.result_count}</td>
            <td className="py-1.5 pr-3 text-destructive type-caption">{attempt.error ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function RunDetailView({ runId, onBack }: RunDetailViewProps) {
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setSnapshot(null);
      try {
        const result = await getRunSnapshot(runId);
        if (cancelled) return;
        setSnapshot(result);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const audit = snapshot?.audit as unknown as AuditReport | null | undefined;

  return (
    <div className="flex-1 flex flex-col gap-3 p-4 overflow-y-auto">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft size={14} className="mr-1.5" />
          返回
        </Button>
        <span className="type-caption text-muted-foreground">{runId}</span>
      </div>

      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <span className="type-caption text-muted-foreground">loading…</span>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-destructive bg-destructive/10 text-destructive text-sm px-3 py-2">
          {error}
        </div>
      )}

      {snapshot && (
        <>
          <div className="glass-1 border border-border/30 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="type-body font-medium">{snapshot.objective}</span>
              <Badge variant="outline">{snapshot.output_profile}</Badge>
            </div>
            <div className="flex items-center gap-2 flex-wrap type-caption text-muted-foreground">
              {snapshot.created_at && <span>{snapshot.created_at}</span>}
              <Badge variant="secondary">{snapshot.entity_count} entities</Badge>
              <Badge variant="secondary">{snapshot.evidence_count} evidence</Badge>
              <Badge variant="secondary">{snapshot.evidence_chain_count} chains</Badge>
              <Badge variant="secondary">{snapshot.hyperedge_count} hyperedges</Badge>
              <Badge variant="secondary">{snapshot.query_family_count} query families</Badge>
            </div>

            {audit && (
              <div>
                <button
                  type="button"
                  onClick={() => setAuditOpen((v) => !v)}
                  className="type-caption text-primary hover:underline"
                >
                  {auditOpen ? "隱藏 audit" : "顯示 audit"}
                </button>
                {auditOpen && (
                  <div className="pt-2 space-y-2 text-xs-minus">
                    {Object.keys(audit.metrics).length > 0 && (
                      <table className="border-collapse">
                        <tbody>
                          {Object.entries(audit.metrics).map(([key, value]) => (
                            <tr key={key}>
                              <td className="pr-3 text-muted-foreground">{key}</td>
                              <td>{value}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    {audit.notes.length > 0 && (
                      <ul className="list-disc list-inside text-muted-foreground">
                        {audit.notes.map((note, i) => (
                          <li key={i}>{note}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <Tabs defaultValue="entities" className="flex-1 min-h-0">
            <TabsList>
              <TabsTrigger value="entities">Entities</TabsTrigger>
              <TabsTrigger value="queries">Queries</TabsTrigger>
              <TabsTrigger value="hyperedges">Hyperedges</TabsTrigger>
              <TabsTrigger value="sources">Sources</TabsTrigger>
            </TabsList>
            <TabsContent value="entities">
              <EntitiesTab snapshot={snapshot} />
            </TabsContent>
            <TabsContent value="queries">
              <QueriesTab snapshot={snapshot} />
            </TabsContent>
            <TabsContent value="hyperedges">
              <HyperedgesTab snapshot={snapshot} />
            </TabsContent>
            <TabsContent value="sources">
              <SourcesTab snapshot={snapshot} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
