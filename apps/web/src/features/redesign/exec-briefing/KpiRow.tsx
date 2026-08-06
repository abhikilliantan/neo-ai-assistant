import { Bot, DollarSign, TrendingUp, Users, Wallet } from "lucide-react";
import { MiniBars, Sparkline } from "@/features/redesign/components";
import { KpiTile } from "./KpiTile";

const revSpark = [10, 13, 12, 17, 16, 21, 24, 23, 28, 31, 34, 40];
const cashSpark = [12, 14, 13, 18, 20, 19, 24, 26, 30, 33, 36, 41];
const pipeSpark = [8, 12, 11, 15, 19, 18, 24, 28, 31, 35, 39, 46];
const aiSpark = [14, 18, 16, 22, 20, 26, 30, 28, 34, 38, 42, 48];
const empBars = [6, 10, 5, 12, 8, 14, 9, 16, 11, 18, 13, 20];

interface Props {
  projectsHealth: number | null;
  overviewsReady: boolean;
}

export function KpiRow({ projectsHealth, overviewsReady }: Props) {
  const healthReal = overviewsReady && projectsHealth != null;
  const healthValue = healthReal ? Math.round(projectsHealth) : 85;

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
      <KpiTile
        icon={TrendingUp}
        tone="cyan"
        label="Total Revenue (MTD)"
        value="$1.24M"
        delta={18.6}
        note="vs last month"
      >
        <Sparkline data={revSpark} color="cyan" height={40} />
      </KpiTile>

      <KpiTile
        icon={Wallet}
        tone="green"
        label="Cash Position"
        value="$2.54M"
        delta={8.3}
        note="vs last month"
      >
        <Sparkline data={cashSpark} color="green" height={40} />
      </KpiTile>

      <KpiTile
        icon={DollarSign}
        tone="violet"
        label="Sales Pipeline"
        value="$7.82M"
        delta={24.7}
        note="vs last month"
      >
        <Sparkline data={pipeSpark} color="violet" height={40} />
      </KpiTile>

      <KpiTile
        icon={TrendingUp}
        tone="cyan"
        label="Projects Health"
        value={`${healthValue}%`}
        delta={6}
        note="vs last month"
        ring={healthValue}
      />

      <KpiTile
        icon={Users}
        tone="amber"
        label="Employees"
        value="156"
        deltaText="+12 new"
        note="vs last month"
      >
        <MiniBars data={empBars} color="amber" height={40} />
      </KpiTile>

      <KpiTile
        icon={Bot}
        tone="violet"
        label="AI Usage (Today)"
        value="78%"
        delta={15}
        note="vs yesterday"
      >
        <Sparkline data={aiSpark} color="violet" height={40} />
      </KpiTile>
    </div>
  );
}
