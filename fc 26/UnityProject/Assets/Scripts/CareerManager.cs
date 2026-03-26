using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public enum CareerState
{
    Menu,
    Hub,
    Transfers,
    Lineup,
    Match
}

[Serializable]
public class PlayerData
{
    public string name;
    public string pos;
    public int rating;
}

[Serializable]
public class TeamData
{
    public string name;
    public int rating;
    public int budget;
    public List<PlayerData> roster = new List<PlayerData>();
    public List<PlayerData> startingXI = new List<PlayerData>();
    public int pts;
    public int gf;
    public int ga;
}

public class CareerManager : MonoBehaviour
{
    public UIManager ui;
    public MatchManager match;

    public CareerState state = CareerState.Menu;
    public int weekIndex = 0;

    private List<TeamData> teams = new List<TeamData>();
    private List<(int home, int away)>[] schedule;
    private int userTeamIndex = 0;

    private List<PlayerData> transferMarket = new List<PlayerData>();
    private System.Random rng = new System.Random();
    private bool initialized = false;

    public void Init(UIManager uiRef, MatchManager matchRef)
    {
        ui = uiRef;
        match = matchRef;
        if (initialized) return;
        initialized = true;
        BuildTeams();
        BuildSchedule();
        RefreshMarket();
        ShowMenu();
    }

    void Start()
    {
        if (initialized) return;
        var uiFound = FindObjectOfType<UIManager>();
        var matchFound = FindObjectOfType<MatchManager>();
        if (uiFound != null && matchFound != null)
        {
            Init(uiFound, matchFound);
        }
    }

    void Update()
    {
        if (!initialized) return;

        if (state == CareerState.Match)
        {
            if (match.matchFinished)
            {
                EndMatchAndReturn();
            }
            if (Input.GetKeyDown(KeyCode.H))
            {
                EndMatchAndReturn();
            }
            return;
        }

        if (state == CareerState.Menu)
        {
            if (Input.GetKeyDown(KeyCode.LeftArrow)) userTeamIndex = (userTeamIndex + teams.Count - 1) % teams.Count;
            if (Input.GetKeyDown(KeyCode.RightArrow)) userTeamIndex = (userTeamIndex + 1) % teams.Count;
            if (Input.GetKeyDown(KeyCode.Return))
            {
                state = CareerState.Hub;
                ShowHub();
            }
            ShowMenu();
            return;
        }

        if (Input.GetKeyDown(KeyCode.Alpha1)) { state = CareerState.Hub; ShowHub(); }
        if (Input.GetKeyDown(KeyCode.Alpha2)) { state = CareerState.Transfers; ShowTransfers(); }
        if (Input.GetKeyDown(KeyCode.Alpha3)) { state = CareerState.Lineup; ShowLineup(); }

        if (state == CareerState.Hub)
        {
            if (Input.GetKeyDown(KeyCode.Space))
            {
                StartMatch();
            }
            if (Input.GetKeyDown(KeyCode.S))
            {
                SimulateWeek();
                ShowHub();
            }
        }
        else if (state == CareerState.Transfers)
        {
            if (Input.GetKeyDown(KeyCode.R))
            {
                RefreshMarket();
                ShowTransfers();
            }
            if (Input.GetKeyDown(KeyCode.B))
            {
                BuyFirstAffordable();
                ShowTransfers();
            }
        }
        else if (state == CareerState.Lineup)
        {
            if (Input.GetKeyDown(KeyCode.T))
            {
                AutoPickXI();
                ShowLineup();
            }
        }
    }

    void BuildTeams()
    {
        var db = TeamDatabase.Load();
        if (db != null && db.teams != null && db.teams.Count > 0)
        {
            foreach (var t in db.teams)
            {
                var td = new TeamData();
                td.name = t.name;
                td.rating = t.overall > 0 ? t.overall : t.rating_base;
                td.budget = 80;
                foreach (var p in t.roster)
                {
                    td.roster.Add(new PlayerData { name = p.name, pos = p.pos, rating = p.rating });
                }
                td.startingXI = td.roster.Take(11).ToList();
                teams.Add(td);
            }
            return;
        }

        string[] names = {
            "Arsenal","Aston Villa","AFC Bournemouth","Brentford","Brighton",
            "Burnley","Chelsea","Crystal Palace","Everton","Fulham",
            "Liverpool","Leeds United","Man City","Man United","Newcastle",
            "Nottingham Forest","Sunderland","Tottenham","West Ham","Wolves"
        };
        int[] ratings = {88,80,71,78,79,66,85,76,74,76,90,72,91,86,82,69,65,84,77,73};

        for (int i = 0; i < names.Length; i++)
        {
            var t = new TeamData();
            t.name = names[i];
            t.rating = ratings[i];
            t.budget = 80;
            t.roster = GenerateRoster(names[i], ratings[i]);
            t.startingXI = t.roster.Take(11).ToList();
            teams.Add(t);
        }
    }

    List<PlayerData> GenerateRoster(string team, int baseRating)
    {
        var list = new List<PlayerData>();
        string[] positions = {"GK","LB","CB","CB","RB","CM","CM","CM","LW","ST","RW"};
        for (int i = 0; i < 22; i++)
        {
            var p = new PlayerData();
            p.name = team + " Player " + (i + 1);
            p.pos = positions[i % positions.Length];
            int jitter = rng.Next(-6, 7);
            p.rating = Mathf.Clamp(baseRating + jitter, 50, 95);
            list.Add(p);
        }
        return list.OrderByDescending(x => x.rating).ToList();
    }

    void BuildSchedule()
    {
        int n = teams.Count;
        var rounds = new List<(int home, int away)>[ (n - 1) * 2 ];
        var list = Enumerable.Range(0, n).ToList();
        int half = n / 2;
        for (int round = 0; round < n - 1; round++)
        {
            var fixtures = new List<(int home, int away)>();
            for (int i = 0; i < half; i++)
            {
                int home = list[i];
                int away = list[n - 1 - i];
                if (round % 2 == 0) fixtures.Add((home, away));
                else fixtures.Add((away, home));
            }
            rounds[round] = fixtures;

            int last = list[n - 1];
            list.RemoveAt(n - 1);
            list.Insert(1, last);
        }
        for (int round = 0; round < n - 1; round++)
        {
            rounds[round + (n - 1)] = rounds[round].Select(f => (f.away, f.home)).ToList();
        }
        schedule = rounds;
    }

    void RefreshMarket()
    {
        transferMarket.Clear();
        for (int i = 0; i < 12; i++)
        {
            var p = new PlayerData();
            p.name = "Free Agent " + (i + 1);
            p.pos = "ANY";
            p.rating = rng.Next(60, 86);
            transferMarket.Add(p);
        }
    }

    void AutoPickXI()
    {
        var team = teams[userTeamIndex];
        team.startingXI = team.roster.OrderByDescending(p => p.rating).Take(11).ToList();
    }

    void BuyFirstAffordable()
    {
        var team = teams[userTeamIndex];
        if (transferMarket.Count == 0) return;
        var p = transferMarket[0];
        int cost = Mathf.Max(10, p.rating - 50);
        if (team.budget >= cost)
        {
            team.budget -= cost;
            team.roster.Add(p);
            team.roster = team.roster.OrderByDescending(x => x.rating).ToList();
            transferMarket.RemoveAt(0);
        }
    }

    void SimulateWeek()
    {
        if (weekIndex >= schedule.Length) return;
        foreach (var (home, away) in schedule[weekIndex])
        {
            int h = SimulateScore(teams[home].rating, teams[away].rating);
            int a = SimulateScore(teams[away].rating, teams[home].rating);
            ApplyResult(home, away, h, a);
        }
        weekIndex += 1;
    }

    int SimulateScore(int ratingA, int ratingB)
    {
        float baseGoals = 1.2f + (ratingA - ratingB) * 0.03f;
        baseGoals = Mathf.Clamp(baseGoals, 0.3f, 3.5f);
        return Mathf.Clamp(Mathf.RoundToInt(UnityEngine.Random.Range(0f, baseGoals + 1.2f)), 0, 6);
    }

    void ApplyResult(int home, int away, int h, int a)
    {
        var th = teams[home];
        var ta = teams[away];
        th.gf += h; th.ga += a;
        ta.gf += a; ta.ga += h;
        if (h > a) th.pts += 3;
        else if (a > h) ta.pts += 3;
        else { th.pts += 1; ta.pts += 1; }
    }

    void StartMatch()
    {
        if (weekIndex >= schedule.Length) return;
        var userTeam = teams[userTeamIndex];
        var fixture = schedule[weekIndex].First(f => f.home == userTeamIndex || f.away == userTeamIndex);
        int homeIdx = fixture.home;
        int awayIdx = fixture.away;

        match.matchActive = true;
        match.matchFinished = false;
        match.ResetMatch();
        match.SetTeams(teams[homeIdx].name, teams[awayIdx].name);
        state = CareerState.Match;
        if (ui != null)
        {
            ui.ShowCareerPanels(false);
            ui.AddCommentary($"{teams[homeIdx].name} vs {teams[awayIdx].name}");
        }
    }

    void EndMatchAndReturn()
    {
        var userTeam = teams[userTeamIndex];
        var fixture = schedule[weekIndex].First(f => f.home == userTeamIndex || f.away == userTeamIndex);
        int homeIdx = fixture.home;
        int awayIdx = fixture.away;

        var score = match.GetScore();
        int h = score.home;
        int a = score.away;
        ApplyResult(homeIdx, awayIdx, h, a);

        weekIndex += 1;
        match.matchActive = false;
        match.matchFinished = false;
        match.ResetMatch();

        state = CareerState.Hub;
        ShowHub();
    }

    void ShowMenu()
    {
        if (ui == null) return;
        ui.ShowCareerPanels(true);
        ui.SetMenuText($"Select Team: {teams[userTeamIndex].name}\nLeft/Right to change\nEnter to start");
        ui.SetHubText("");
        ui.SetTransfersText("");
        ui.SetLineupText("");
        ui.SetTableText("");
    }

    void ShowHub()
    {
        if (ui == null) return;
        var userTeam = teams[userTeamIndex];
        var next = GetNextFixture(userTeamIndex);
        string fixture = next.HasValue ? $"{teams[next.Value.home].name} vs {teams[next.Value.away].name}" : "Season complete";
        ui.SetHubText($"Week {weekIndex + 1}/{schedule.Length}\nNext: {fixture}\nBudget: £{userTeam.budget}m\n\nSpace: play match\nS: simulate week\n1 Hub 2 Transfers 3 Lineup");
        ui.SetMenuText("");
        ui.SetTransfersText("");
        ui.SetLineupText("");
        ui.SetTableText(BuildTable());
    }

    void ShowTransfers()
    {
        if (ui == null) return;
        var userTeam = teams[userTeamIndex];
        string list = string.Join("\n", transferMarket.Select(p => $"{p.name} ({p.rating})"));
        ui.SetTransfersText($"Budget: £{userTeam.budget}m\nB: buy top player\nR: refresh\n\n{list}");
        ui.SetMenuText("");
        ui.SetHubText("");
        ui.SetLineupText("");
        ui.SetTableText("");
    }

    void ShowLineup()
    {
        if (ui == null) return;
        var team = teams[userTeamIndex];
        string xi = string.Join("\n", team.startingXI.Select(p => $"{p.name} ({p.pos}) {p.rating}"));
        ui.SetLineupText($"Starting XI\nT: auto-pick best\n\n{xi}");
        ui.SetMenuText("");
        ui.SetHubText("");
        ui.SetTransfersText("");
        ui.SetTableText("");
    }

    string BuildTable()
    {
        var sorted = teams.OrderByDescending(t => t.pts).ThenByDescending(t => t.gf - t.ga).ToList();
        string table = "Table\n";
        for (int i = 0; i < sorted.Count; i++)
        {
            var t = sorted[i];
            table += $"{i + 1}. {t.name} {t.pts}pts GD {t.gf - t.ga}\n";
        }
        return table;
    }

    (int home, int away)? GetNextFixture(int teamIndex)
    {
        if (weekIndex >= schedule.Length) return null;
        foreach (var f in schedule[weekIndex])
        {
            if (f.home == teamIndex || f.away == teamIndex) return f;
        }
        return null;
    }
}
