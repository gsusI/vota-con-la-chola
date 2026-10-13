// Voting-aid styles load only on /citizen/vota/: editing them must not rehash the CSS every page links.
import "./votingAid.css";

export default function VotingAidLayout({ children }) {
  return children;
}
