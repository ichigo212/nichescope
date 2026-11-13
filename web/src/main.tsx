import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { Layout } from "./components/Layout";
import { startEvents } from "./events";
import { ChannelPage } from "./pages/Channel";
import { HomePage } from "./pages/Home";
import { MeshPage } from "./pages/Mesh";
import { ProjectPage } from "./pages/Project";
import { ProjectsPage } from "./pages/Projects";
import { NotFound, RouteError } from "./pages/NotFound";
import { SettingsPage } from "./pages/Settings";
import { ToolsPage } from "./pages/Tools";
import "./theme/index.css";

startEvents();

const router = createBrowserRouter([
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/c/:id", element: <ChannelPage /> },
      { path: "/c/:id/topics/:run", element: <ChannelPage /> },
      { path: "/c/:id/:tab", element: <ChannelPage /> },
      { path: "/projects", element: <ProjectsPage /> },
      { path: "/projects/:id", element: <ProjectPage /> },
      { path: "/mesh", element: <MeshPage /> },
      { path: "/tools", element: <ToolsPage /> },
      { path: "/settings", element: <SettingsPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
