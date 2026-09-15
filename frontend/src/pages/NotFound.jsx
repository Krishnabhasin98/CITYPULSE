import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, EmptyState, PageHeader } from "../components/ui";

export default function NotFound() {
  return (
    <>
      <PageHeader eyebrow="404" title="That page does not exist" description="The link may be old, or the page moved when the app was reorganised." />
      <EmptyState
        icon={Compass}
        title="Nothing to show here"
        message="Try the live incident map, area intelligence, or the accountability queue."
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Link to="/">
              <Button>Back to home</Button>
            </Link>
            <Link to="/map">
              <Button variant="secondary">Open the map</Button>
            </Link>
          </div>
        }
      />
    </>
  );
}
