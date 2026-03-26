using UnityEngine;

public enum TeamSide
{
    Home,
    Away
}

public class PlayerController : MonoBehaviour
{
    public TeamSide team;
    public int number;
    public bool isGoalkeeper;
    public bool isUserControlled;

    [HideInInspector] public Vector3 homePosition;

    private Rigidbody rb;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
    }

    public void MoveToward(Vector3 target, float speed)
    {
        Vector3 dir = (target - transform.position);
        dir.y = 0f;
        if (dir.sqrMagnitude < 0.01f)
        {
            rb.linearVelocity = Vector3.Lerp(rb.linearVelocity, Vector3.zero, 0.2f);
            return;
        }
        dir = dir.normalized;
        Vector3 desired = dir * speed;
        rb.linearVelocity = Vector3.MoveTowards(rb.linearVelocity, desired, GameConfig.PlayerAccel * Time.deltaTime);
        if (dir != Vector3.zero)
        {
            transform.rotation = Quaternion.LookRotation(dir, Vector3.up);
        }
    }

    public void Stop()
    {
        rb.linearVelocity = Vector3.Lerp(rb.linearVelocity, Vector3.zero, 0.3f);
    }
}
