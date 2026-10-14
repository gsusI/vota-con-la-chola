// Voting-aid styles load only on /citizen/vota/: editing them must not rehash the CSS every page links.
import "./votaShell.css";
import "./votingAid.css";
import VotaShell from "./VotaShell";

export default function VotingAidLayout({ children }) {
  return (
    <div className="vota">
      <VotaShell />
      {children}
    </div>
  );
}
