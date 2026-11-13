import { Link, useRouteError } from "react-router-dom";

import { Empty, buttonClass } from "../components/ui";

export function NotFound() {
  return (
    <Empty
      title="Page not found"
      body="This address does not match a page."
      action={
        <Link to="/" className={buttonClass("secondary")}>
          Back to channels
        </Link>
      }
    />
  );
}

export function RouteError() {
  const error = useRouteError();
  return (
    <div className="mx-auto max-w-xl px-6 pt-24">
      <Empty
        title="Something went wrong on this page"
        body={error instanceof Error ? error.message : String(error)}
        action={
          <a href="/" className={buttonClass("secondary")}>
            Back to channels
          </a>
        }
      />
    </div>
  );
}
