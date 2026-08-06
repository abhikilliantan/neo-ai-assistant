import { CompanyStatusCard, SampleTag, SectionHeader } from "@/features/redesign/components";
import type { SparkColor } from "@/features/redesign/components";
import type { CompanyStatus } from "./data";
import { SAMPLE_COMPANIES, SAMPLE_COMPANY_META } from "./data";

const SPARK = [22, 26, 24, 30, 28, 34, 33, 39, 42, 40, 45, 48];
const COLORS: SparkColor[] = ["green", "cyan", "amber", "violet"];

interface Props {
  companyStatuses: CompanyStatus[];
  companiesReady: boolean;
}

export function LiveCompanyStatus({ companyStatuses, companiesReady }: Props) {
  const useReal = companiesReady && companyStatuses.length > 0;

  return (
    <section>
      <SectionHeader
        title="Live Company Status"
        subtitle={useReal ? "Names & health % are live; revenue is sample" : undefined}
        action={useReal ? undefined : <SampleTag />}
      />
      {/* 2-up: the ring-left CompanyStatusCard needs room to breathe (4-up
          starves the name column). Still one clean grid of all four. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {useReal
          ? companyStatuses.map((cs, i) => {
              const key = cs.company.name.split(/\s+/)[0].toLowerCase();
              const meta = SAMPLE_COMPANY_META[key];
              return (
                <CompanyStatusCard
                  key={cs.company.id}
                  name={cs.company.name}
                  percent={cs.progress ?? 80}
                  revenue={meta?.revenue ?? 250_000}
                  trend={SPARK}
                  color={COLORS[i % COLORS.length]}
                  sample // revenue + trend have no endpoint yet
                />
              );
            })
          : SAMPLE_COMPANIES.map((c) => (
              <CompanyStatusCard
                key={c.name}
                name={c.name}
                percent={c.percent}
                revenue={c.revenue}
                delta={c.delta}
                trend={SPARK}
                color={c.color}
                sample
              />
            ))}
      </div>
    </section>
  );
}
