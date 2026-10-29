import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { RoutingSettings } from "@/features/settings/components/routing-settings";
import { createDashboardSettings } from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";
import { RoutingWeightSettings } from "./weight-settings";

describe("custom weight and remaining quota routing", () => {
  beforeEach(() => useAuthStore.setState({role:"admin",canWrite:true,authenticated:true}));
  it("selects the new strategy through the existing settings update", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<RoutingSettings settings={createDashboardSettings()} busy={false} onSave={onSave} />);
    await userEvent.setup().click(screen.getByRole("button", {name:/Custom weight × remaining quota/}));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({routingStrategy:"custom_weighted_quota"}));
  });
  it("saves fractional real-account weights and zero source weights", async () => {
    const entries = [
      {accountId:"account-1",name:"Account A",kind:"account",weight:1},
      {accountId:"model-source:src-1",name:"Compass",kind:"model_source",weight:1},
    ];
    const updates: Array<{id:string;weight:number}> = [];
    server.use(
      http.get("/api/relay-routing/weights",()=>HttpResponse.json({accounts:entries})),
      http.put("/api/relay-routing/weights/:id",async ({request,params})=>{
        const body = await request.json() as {weight:number};
        updates.push({id:String(params.id),weight:body.weight});
        const entry=entries.find(item=>item.accountId===params.id)!;
        entry.weight=body.weight;
        return HttpResponse.json(body);
      }),
    );
    const user=userEvent.setup();
    renderWithProviders(<RoutingWeightSettings />);
    const a=await screen.findByRole("spinbutton",{name:"Routing weight for Account A"});
    await user.clear(a); await user.type(a,"2.5");
    await user.click(screen.getAllByRole("button",{name:"Save"})[0]);
    await waitFor(()=>expect(updates).toContainEqual({id:"account-1",weight:2.5}));
    const source=screen.getByRole("spinbutton",{name:"Routing weight for Compass"});
    await user.clear(source); await user.type(source,"0");
    await user.click(screen.getAllByRole("button",{name:"Save"})[1]);
    await waitFor(()=>expect(updates).toContainEqual({id:"model-source:src-1",weight:0}));
  });
  it("rejects negative weights before sending and scopes single-account controls", async () => {
    server.use(http.get("/api/relay-routing/weights",()=>HttpResponse.json({accounts:[
      {accountId:"a",name:"A",kind:"account",weight:1},
      {accountId:"b",name:"B",kind:"account",weight:1},
    ]})));
    const user=userEvent.setup();
    renderWithProviders(<RoutingWeightSettings accountId="a" />);
    const input=await screen.findByRole("spinbutton",{name:"Routing weight for A"});
    expect(screen.queryByRole("spinbutton",{name:"Routing weight for B"})).not.toBeInTheDocument();
    await user.clear(input); await user.type(input,"-1");
    expect(screen.getByRole("button",{name:"Save"})).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("finite number");
  });
  it("does not expose weight controls to a visitor", () => {
    useAuthStore.setState({role:"guest",canWrite:false});
    const {container}=renderWithProviders(<RoutingWeightSettings />);
    expect(container).toBeEmptyDOMElement();
  });
  it("explains probability, minimum quota and the placeholder without fetching priority rules", async () => {
    const rules = vi.fn(() => HttpResponse.json({plans:[],accounts:[]}));
    server.use(
      http.get("/api/relay-routing/weights", () => HttpResponse.json({accounts:[]})),
      http.get("/api/relay-routing/rules", rules),
    );
    renderWithProviders(<RoutingWeightSettings />);
    expect(screen.getByText(/Scores define random probabilities/)).toBeInTheDocument();
    expect(screen.getByText(/square of the lowest applicable/)).toBeInTheDocument();
    expect(screen.getByText(/lowest applicable remaining quota fraction/)).toBeInTheDocument();
    expect(screen.getByText(/100% is only a routing placeholder/)).toBeInTheDocument();
    expect(screen.queryByText("Plan and account priority rules")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Loading...")).not.toBeInTheDocument());
    expect(rules).not.toHaveBeenCalled();
  });
});
