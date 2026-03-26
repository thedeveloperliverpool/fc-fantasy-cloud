using System.Collections.Generic;
using UnityEngine;

public class MatchManager : MonoBehaviour
{
    public List<PlayerController> home = new List<PlayerController>();
    public List<PlayerController> away = new List<PlayerController>();
    public BallController ball;
    public UIManager ui;
    public bool matchActive = false;
    public bool matchFinished = false;

    private PlayerController user;
    private bool paused = false;
    private float matchTime = 0f;
    private int scoreHome = 0;
    private int scoreAway = 0;

    private TeamSide lastTouchTeam = TeamSide.Home;
    private bool kickoffPending = false;
    private PlayerController kickoffOwner;
    private bool setpieceActive = false;
    private TeamSide setpieceTeam;
    private string setpieceType = ""; // throw, corner, goalkick

    private const float HalfLength = 30f;
    private int half = 1;

    public string currentHomeName = "HOME";
    public string currentAwayName = "AWAY";

    public void SetTeams(string homeName, string awayName)
    {
        currentHomeName = homeName;
        currentAwayName = awayName;
    }

    public (int home, int away) GetScore()
    {
        return (scoreHome, scoreAway);
    }

    public void ResetMatch()
    {
        matchTime = 0f;
        scoreHome = 0;
        scoreAway = 0;
        matchFinished = false;
        half = 1;
        kickoffPending = true;
        if (ui != null)
        {
            ui.SetScore(scoreHome, scoreAway);
            ui.SetTime(RemainingTime());
            ui.ShowCareerPanels(true);
        }
    }

    void Start()
    {
        if (home.Count > 0)
        {
            user = home[10];
            user.isUserControlled = true;
            AddControlIndicator(user);
        }
        if (ui != null)
        {
            ui.SetScore(scoreHome, scoreAway);
            ui.SetTime(RemainingTime());
            ui.BindMiniMap(home, away);
        }
        ResetKickoff(true);
    }

    void Update()
    {
        if (!matchActive)
        {
            if (ui != null) ui.TickCommentary(Time.deltaTime);
            return;
        }

        if (Input.GetKeyDown(KeyCode.Escape))
        {
            paused = !paused;
            if (ui != null) ui.SetPaused(paused);
        }
        if (paused)
        {
            if (ui != null) ui.TickCommentary(Time.deltaTime);
            return;
        }

        matchTime += Time.deltaTime;
        if (ui != null) ui.SetTime(RemainingTime());

        if (matchTime >= HalfLength)
        {
            if (half == 1)
            {
                half = 2;
                matchTime = 0f;
                Say("Halftime");
                ResetKickoff(false);
            }
            else
            {
                matchFinished = true;
                matchActive = false;
                Say("Full Time");
                return;
            }
        }

        UpdatePossession();
        HandleUserInput();
        UpdateAI(home, TeamSide.Home, false);
        UpdateAI(away, TeamSide.Away, true);
        ClampPlayers();
        CheckGoals();
        CheckOutOfBounds();
        if (ui != null)
        {
            ui.UpdateMiniMap(home, away, ball);
            ui.TickCommentary(Time.deltaTime);
        }
    }

    float RemainingTime()
    {
        return Mathf.Max(0f, HalfLength - matchTime);
    }

    void UpdatePossession()
    {
        if (ball.owner != null) return;
        foreach (var p in home)
        {
            if ((p.transform.position - ball.transform.position).sqrMagnitude <= GameConfig.ControlRadius * GameConfig.ControlRadius)
            {
                ball.owner = p;
                lastTouchTeam = p.team;
                return;
            }
        }
        foreach (var p in away)
        {
            if ((p.transform.position - ball.transform.position).sqrMagnitude <= GameConfig.ControlRadius * GameConfig.ControlRadius)
            {
                ball.owner = p;
                lastTouchTeam = p.team;
                return;
            }
        }
    }

    void HandleUserInput()
    {
        if (user == null) return;
        Vector3 input = Vector3.zero;
        if (Input.GetKey(KeyCode.LeftArrow)) input.x = -1f;
        if (Input.GetKey(KeyCode.RightArrow)) input.x = 1f;
        if (Input.GetKey(KeyCode.UpArrow)) input.z = 1f;
        if (Input.GetKey(KeyCode.DownArrow)) input.z = -1f;

        if (input.sqrMagnitude > 0.01f)
        {
            user.MoveToward(user.transform.position + input.normalized, GameConfig.PlayerSpeed);
        }
        else
        {
            user.Stop();
        }

        if (Input.GetKeyDown(KeyCode.Space))
        {
            var target = FindBestPassTarget(user, home, TeamSide.Home);
            if (target != null && ball.owner == user)
            {
                Vector3 dir = (target.transform.position - ball.transform.position);
                ball.Kick(dir, GameConfig.BallKickSpeed);
                lastTouchTeam = user.team;
                if (kickoffPending && kickoffOwner == user) kickoffPending = false;
                setpieceActive = false;
                Say("Pass to " + target.number);
            }
        }

        if (Input.GetKeyDown(KeyCode.K))
        {
            if (ball.owner == user)
            {
                Vector3 goal = new Vector3(0f, 0f, GameConfig.FieldLength * 0.5f);
                Vector3 dir = (goal - ball.transform.position);
                ball.Kick(dir, GameConfig.BallShootSpeed);
                lastTouchTeam = user.team;
                if (kickoffPending && kickoffOwner == user) kickoffPending = false;
                setpieceActive = false;
                Say("Shot!");
            }
        }
    }

    void UpdateAI(List<PlayerController> team, TeamSide side, bool attackDown)
    {
        Vector3 goal = new Vector3(0f, 0f, attackDown ? -GameConfig.FieldLength * 0.5f : GameConfig.FieldLength * 0.5f);
        bool teamHasBall = ball.owner != null && ball.owner.team == side;

        for (int i = 0; i < team.Count; i++)
        {
            var p = team[i];
            if (p.isUserControlled) continue;

            if (teamHasBall && ball.owner == p)
            {
                float distToGoal = Vector3.Distance(p.transform.position, goal);
                if (distToGoal < 20f)
                {
                    ball.Kick(goal - p.transform.position, GameConfig.BallShootSpeed);
                    lastTouchTeam = p.team;
                    if (kickoffPending && kickoffOwner == p) kickoffPending = false;
                    setpieceActive = false;
                    Say("AI shot");
                    continue;
                }
                if (Random.value < 0.4f)
                {
                    var target = FindBestPassTarget(p, team, side);
                    if (target != null)
                    {
                        ball.Kick(target.transform.position - p.transform.position, GameConfig.BallKickSpeed);
                        lastTouchTeam = p.team;
                        if (kickoffPending && kickoffOwner == p) kickoffPending = false;
                        setpieceActive = false;
                        continue;
                    }
                }
                p.MoveToward(goal, GameConfig.PlayerSpeed * 0.9f);
            }
            else
            {
                bool chase = IsChasingBall(p, side);
                if (chase && !setpieceActive)
                {
                    p.MoveToward(ball.transform.position, GameConfig.PlayerSpeed);
                }
                else
                {
                    p.MoveToward(p.homePosition, GameConfig.PlayerSpeed * 0.7f);
                }
            }
        }
    }

    bool IsChasingBall(PlayerController p, TeamSide side)
    {
        List<PlayerController> team = side == TeamSide.Home ? home : away;
        team.Sort((a, b) =>
            (a.transform.position - ball.transform.position).sqrMagnitude
            .CompareTo((b.transform.position - ball.transform.position).sqrMagnitude));
        for (int i = 0; i < team.Count && i < 3; i++)
        {
            if (team[i] == p) return true;
        }
        return false;
    }

    PlayerController FindBestPassTarget(PlayerController from, List<PlayerController> team, TeamSide side)
    {
        PlayerController best = null;
        float bestScore = -999f;
        foreach (var p in team)
        {
            if (p == from) continue;
            float dist = Vector3.Distance(from.transform.position, p.transform.position);
            if (dist > 25f) continue;
            float forward = (side == TeamSide.Home ? p.transform.position.z : -p.transform.position.z);
            float score = forward - dist * 0.2f + Random.Range(-1f, 1f);
            if (score > bestScore)
            {
                bestScore = score;
                best = p;
            }
        }
        return best;
    }

    void CheckGoals()
    {
        if (ball.owner != null) return;
        float z = ball.transform.position.z;
        float x = ball.transform.position.x;
        if (z > GameConfig.FieldLength * 0.5f && Mathf.Abs(x) < GameConfig.GoalWidth * 0.5f)
        {
            scoreHome += 1;
            if (ui != null) ui.SetScore(scoreHome, scoreAway);
            Say("GOAL for HOME!");
            ResetKickoff(false);
        }
        if (z < -GameConfig.FieldLength * 0.5f && Mathf.Abs(x) < GameConfig.GoalWidth * 0.5f)
        {
            scoreAway += 1;
            if (ui != null) ui.SetScore(scoreHome, scoreAway);
            Say("GOAL for AWAY!");
            ResetKickoff(true);
        }
    }

    void CheckOutOfBounds()
    {
        if (ball.owner != null) return;
        float halfL = GameConfig.FieldLength * 0.5f;
        float halfW = GameConfig.FieldWidth * 0.5f;
        Vector3 pos = ball.transform.position;

        if (pos.x < -halfW || pos.x > halfW)
        {
            TeamSide throwTeam = lastTouchTeam == TeamSide.Home ? TeamSide.Away : TeamSide.Home;
            setpieceActive = true;
            setpieceTeam = throwTeam;
            setpieceType = "throw";
            pos.x = Mathf.Clamp(pos.x, -halfW, halfW);
            ball.transform.position = new Vector3(pos.x, 0.2f, pos.z);
            AssignSetpieceTaker(throwTeam);
            Say("Throw-in");
            return;
        }

        if (pos.z > halfL || pos.z < -halfL)
        {
            bool isHomeGoalLine = pos.z > halfL;
            TeamSide defending = isHomeGoalLine ? TeamSide.Home : TeamSide.Away;
            TeamSide attacking = isHomeGoalLine ? TeamSide.Away : TeamSide.Home;

            if (lastTouchTeam == defending)
            {
                setpieceType = "corner";
                setpieceTeam = attacking;
                setpieceActive = true;
                ball.transform.position = new Vector3(Mathf.Sign(pos.x) * (halfW - 0.5f), 0.2f, isHomeGoalLine ? halfL - 0.5f : -halfL + 0.5f);
                AssignSetpieceTaker(attacking);
                Say("Corner");
            }
            else
            {
                setpieceType = "goalkick";
                setpieceTeam = defending;
                setpieceActive = true;
                ball.transform.position = new Vector3(0f, 0.2f, isHomeGoalLine ? halfL - 8f : -halfL + 8f);
                AssignSetpieceTaker(defending);
                Say("Goal kick");
            }
        }
    }

    void AssignSetpieceTaker(TeamSide team)
    {
        var list = team == TeamSide.Home ? home : away;
        PlayerController taker = list[0];
        float best = float.MaxValue;
        foreach (var p in list)
        {
            float d = (p.transform.position - ball.transform.position).sqrMagnitude;
            if (d < best)
            {
                best = d;
                taker = p;
            }
        }
        foreach (var p in home) p.isUserControlled = (p == user);
        foreach (var p in away) p.isUserControlled = false;
        ball.owner = taker;
    }

    void ResetKickoff(bool homeKickoff)
    {
        ball.owner = null;
        ball.transform.position = Vector3.up * 0.2f;
        ball.GetComponent<Rigidbody>().linearVelocity = Vector3.zero;
        foreach (var p in home)
        {
            p.transform.position = p.homePosition;
            p.GetComponent<Rigidbody>().linearVelocity = Vector3.zero;
        }
        foreach (var p in away)
        {
            p.transform.position = p.homePosition;
            p.GetComponent<Rigidbody>().linearVelocity = Vector3.zero;
        }
        kickoffPending = true;
        kickoffOwner = homeKickoff ? home[9] : away[9];
        ball.owner = kickoffOwner;
    }

    void ClampPlayers()
    {
        float halfL = GameConfig.FieldLength * 0.5f;
        float halfW = GameConfig.FieldWidth * 0.5f;
        foreach (var p in home)
        {
            var pos = p.transform.position;
            pos.x = Mathf.Clamp(pos.x, -halfW, halfW);
            pos.z = Mathf.Clamp(pos.z, -halfL, halfL);
            p.transform.position = pos;
        }
        foreach (var p in away)
        {
            var pos = p.transform.position;
            pos.x = Mathf.Clamp(pos.x, -halfW, halfW);
            pos.z = Mathf.Clamp(pos.z, -halfL, halfL);
            p.transform.position = pos;
        }
    }

    void Say(string line)
    {
        if (ui != null)
        {
            ui.AddCommentary(line);
        }
    }

    void AddControlIndicator(PlayerController p)
    {
        var ring = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        ring.name = "ControlRing";
        ring.transform.SetParent(p.transform, false);
        ring.transform.localScale = new Vector3(1.6f, 0.02f, 1.6f);
        ring.transform.localPosition = new Vector3(0f, -0.9f, 0f);
        var renderer = ring.GetComponent<Renderer>();
        renderer.material.color = new Color(1f, 0.95f, 0.2f);
        var collider = ring.GetComponent<Collider>();
        if (collider != null) Destroy(collider);
    }
}
